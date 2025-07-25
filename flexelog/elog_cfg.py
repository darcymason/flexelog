# Copyright 2025 flexelog authors. See LICENSE file for details.
from collections import defaultdict
import configparser
import csv
from dataclasses import dataclass, field
import re
from typing import Any
import warnings
import functools

from django.conf import settings
from django.db.models.signals import post_save  # update config when logbook changed
from django.contrib.auth.models import Group
from flexelog.models import ElogConfig, Logbook
from guardian.shortcuts import assign_perm

import logging
logger = logging.getLogger("flexelog")

_cfg = None  # singleton of LogbookConfig class


class ConfigError(Exception):
    pass


class ConfigWarning:
    pass


@dataclass
class Attribute:
    name: str
    required: bool = False
    extendable: bool = False
    options_type: str = (
        "Text"  #  or Options, MOptions, ROptions, IOptions
    )
    options: list[str] = field(default_factory=list)
    # for conditions in other attributes, which values here set what condition
    # e.g. {"Linux": "1", "Windows", "2"}
    val_conditions: dict[str, str] = field(default_factory=dict)
    val_type: str = ""  # psi elog had date | datetime | numeric | userlist | useremail | muserlist | museremail
    
    def __post_init__(self):
        self.parse_conditions()

    def parse_conditions(self):
        # Check for attributes with conditional values, e.g. Opt1{1}, Opt2{a}
        # Separate the {condition} from the name, and store it
        for i, option in enumerate(self.options):
            match = re.search(r"\{(.*?)\}", option)
            if match:
                opt_name = re.sub(r"\{.*?\}", "", option)
                condition = match.groups()[0]
                self.val_conditions[opt_name] = condition
                # Remove the `{<condition>}` from the option name
                self.options[i] = opt_name


# Attributes if none are specified in config
DEFAULT_ATTRIBUTES = {
    # "Author": Attribute("Author", required=True),  -- now have distinct author field
    "Type": Attribute(
        "Type", options_type="Options", options=["Routine", "Other"]
    ),
    "Category": Attribute(
        "Category", options_type="Options", options=["General", "Other"]
    ),
    "Subject": Attribute("Subject"),
}


# Default settings for database ElogConfig settings if not specified
ELOGCONFIG_DEFAULTS = {
    "all display limit": 500,
    "attachment lines": 300,
    "charset": "UTF-8",  # PSI elog default was ISO-8859-1
    "display mode": "summary",  # default mode for search, and used by "Last xxx"
    "entries per page": 20,
    "hide comments": False,  # lb comment on logbook selection page
    # "language": "english", --> define in django settings.py instead
    "list display": "ID, Date, Author, *attributes, Text, Attachments", # *attributes means all Attributes not explicitly listed
    #  "Page Title": "FlexElog Logbook Selection", if global section
    "max content length": 10485760,
    "protect selection page": 0,
    "reverse sort": True,  # different from PSI elog, default is in order
    "search all logbooks": 1,
    "show attachments": True,
    "show text": True, # False = no Text attribute in logbook
    "summary lines": 3,
    "summary line length": 100,  # PSI default was 40
    # date-time displayed for logbook entries,
    # Default in PSI elog was e.g. "09/30/2023 12:57:03 pm"
    "time format": "%m/%d/%Y %I:%M:%S %p",  # likely ignore in favor of locale settings on computer/browser
}


def cfg_bool(s: str | bool) -> bool | str:
    if isinstance(s, bool):
        return s
    if s.strip().lower() in ("1", "on", "true", "yes"):
        return True
    elif s.strip().lower() in ("0", "off", "false", "no"):
        return False
    return s


class LogbookConfig:
    def __init__(self, config_text: str):
        self._config_text = config_text
        self._conditions = []
        self.clear_conditions()
        self.load_config()
        self.parse_config()

    def add_condition(self, condition: str):
        if condition not in self._conditions:
            self._conditions.append(condition.lower())
            self.parse_config()

    def set_conditions_from_attrs(self, lb_name: str, attrs: dict):
        lb_attrs = self.lb_attrs[lb_name]
        have_conditional = False
        for attr, val in attrs.items():
            if not isinstance(val, list):
                val = [val]
            for v in val:
                try:
                    # Note add_condition reparses config'd Attributes available
                    self._conditions.append(lb_attrs[attr].val_conditions[v])
                    have_conditional = True
                except KeyError:
                    pass

        if have_conditional:
            self.parse_config()

    def clear_conditions(self):
        if self._conditions:
            self._conditions = []
            self.parse_config()

    def __enter__(self):
        self.clear_conditions()

    def __exit__(self, exc_type, exc_value, traceback):
        self.clear_conditions()

    def load_config(self):
        # Load `elogd.cfg` style config textfile into self._cfg dict
        # Starts with Python's ConfigParser, so
        # cannot repeat keys (in default 'strict' mode) which is tolerated in psi elog
        # interpolation must be None because of date/time formats with "%"
        self.configp = configparser.ConfigParser(
            default_section="global",
            interpolation=None,
            # ? allow_unnamed_section=True ? and just ignore them?
        )
        self.configp.optionxform = str  # keys are case sensitive
        self.configp.read_string(self._config_text)

        # Determine language translations, if any
        # lang = "english"
        # if "global" in self.configp:
        #     lang = self.configp["global"].get("Language", "english")

        # set_language(HERE / "resources", lang)
        # self.editor.set_lang(iso639_for_language.get(lang.lower(), "en"))

        cp = self.configp

        # Go through all config keys and deal with conditionals
        # All values become a dict mapped by conditions or empty string ""
        # Key = val becomes Key: {"": val}
        # {1} Key = val becomes Key: {"1": val}
        # {1,2} Key = val becomes Key: {"1": val, "2": val}  ("or")
        # {1&2} Key = val becomes Key: {("1", "2"): val}    ("and")
        # Note the conditionals in the *values* are not parsed at this point
        self._cfg = dict()

        for section_name in cp.sections() + ["global"]:
            self._cfg[section_name] = section_dict = defaultdict(dict)
            for key, val in cp[section_name].items():
                # match [{<conditionals>}]<bare_key>
                match = re.search(r"(?:\{(.*?)\})?\s*(.*?)$", key)
                if not match:
                    logger.error(
                        f"Unable to parse config file option '{key}' in section '{section_name}'"
                    )
                    continue
                conditions, bare_key = match.groups()
                bare_key = bare_key.lower()  # to use in case-insensitive `get`
                if conditions is None:
                    section_dict[bare_key][""] = val
                else:
                    conditions = [
                        x.strip().lower() for x in conditions.split(",")
                    ]
                    for condition in conditions:
                        if "&" in condition:
                            condition = tuple(condition.split("&"))
                        section_dict[bare_key][condition] = val

    def parse_config(self):
        self._lb_attrs = {}
        for lb_name in self._cfg:
            # don't include global sections, doing logbooks only
            if lb_name.lower().startswith("global"):
                continue
            if lb_name.lower().startswith("group "):
                logger.warning(
                    f"Found section [{lb_name}] in ElogConfig: "
                    "[Group xxx] sections are ignored in this "
                    "version of FlexElog"
                )
                
            attrs = {
                name: Attribute(name)
                for name in self.get(lb_name, "Attributes", as_list=True)
            }

            if not attrs:
                attrs = DEFAULT_ATTRIBUTES

            self._lb_attrs[lb_name] = attrs

            # Set Required Attributes
            for attr in self.get(lb_name, "Required Attributes", as_list=True):
                if attr not in attrs:
                    warnings.warn(
                        f"Required Attributes '{attr}' is not listed in Attributes line and is ignored"
                    )
                else:
                    attrs[attr].required = True

            # Set Extendable Options (attributes)
            for attr in self.get(lb_name, "Extendable Options", as_list=True):
                if attr not in attrs:
                    logger.warning(
                        f"In config for logbook '{lb_name}', "
                        f"Extendable Options '{attr}' is not listed in Attributes line and is ignored"
                    )
                else:
                    attrs[attr].extendable = True
            
            # Categorize attribute value type e.g. `Type Start date = datetime`
            for attr_name, attr in attrs.items():
                if valtype := self.get(lb_name, f"Type {attr_name}"):
                    attr.val_type = valtype

            # Set the Option Types (Text by default)
            # Logic here means if repeated, last one spec'd wins
            for attr_name, attr in attrs.items():
                for option_type in ["Options", "MOptions", "ROptions", "IOptions"]:
                    # XX below is specific to single space, could make whitespace tolerant
                    options = self.get(
                        lb_name, f"{option_type} {attr_name}", as_list=True
                    )
                    if options:
                        attr.options_type = option_type
                        attr.options = options
                attr.parse_conditions()
            
        # Create Logbook class instance for each logbook
        # self._logbooks = {}
        # For migration only, get paths to original PSI file-based logbooks
        # First get general logbooks dir - location unless Subdir is absolute
        # If not specified in global section, then is under elogd.cfg path / "logbooks"
        # self.logbooks_dir = Path(
        #     self.get(
        #         "global", "Logbook dir", self.filename.parent / "logbooks"
        #     )
        # )

        # for lb_name in self._cfg:
        #     if lb_name.startswith("global"):
        #         continue
            # subdir = Path(self.get(lb_name, "Subdir", default=lb_name))
            # lb_dir = (
            #     subdir if subdir.is_absolute() else self.logbooks_dir / lb_name
            # )

    def get(
        self,
        lb: str | Logbook,
        param: str,
        *,
        default: Any | None = None,
        valtype: type | None = None,
        as_list: bool = False,
    ) -> Any:
        """Return the config key's value based on current conditions (if any)

        First looks in elogd.cfg logbook section,
        then global section (if logbook_only is False),
        then the passed default (e.g. from request.args), if not None,
        then in ELOGCONFIG_DEFAULTS in elog_cfg.py.

        If `valtype` specified, return the ELOGCONFIG_DEFAULTS value if conversion gives an error
        """
        if as_list and default is None:
            default = []

        if valtype is None:
            valtype = str
        if valtype is bool:
            valtype = cfg_bool

        lb_name = lb.name if isinstance(lb, Logbook) else lb  # XX need to clean lb_name?
        if lb_name not in self._cfg:
            logger.warning(f"Unknown config section {lb_name}")
            return default

        param = param.lower()  # make case insensitive

        # Retrieve the requested parameter from logbook section, or global,
        # or defaults.  If none of those, then passed `default`
        if (
            param in self._cfg[lb_name]
        ):  # Note cannot use .get as creates it (defaultdict)
            val_dict = self._cfg[lb_name][param]
        elif param in self._cfg["global"]:
            val_dict = self._cfg["global"][param]
        else:
            # defaults or `default` can't have conditions, so mock no-condition
            val_dict = {"": ELOGCONFIG_DEFAULTS.get(param, default)}

        assert isinstance(
            val_dict, dict
        ), "Error, Config._cfg values must be a dict"

        # Go through conditions in order, fall back to no condition ("")
        for condition in self._conditions:
            try:
                val = val_dict[condition]
                break
            except KeyError:
                continue
        else:  # 'no condition', or global/default assigned above
            val = val_dict.get("", default)
            if val == [] or val is None:
                return val

        # Convert all to list temporarily
        # Can have commas inside a quoted string so use csv to split
        temp_rdr = csv.reader((val,),  delimiter=',', skipinitialspace=True)  # quotechar='"',
        val = (
            [x.strip() for x in next(temp_rdr) if x.strip()]
            if as_list
            else [val]
        )
        if not valtype:
            return val if as_list else val[0]

        return_vals = []
        for v in val:
            try:
                return_vals.append(valtype(v))
            except:
                logger.warning(
                    f"Error converting value {val} with valtype {valtype}. Ignored."
                )

        return return_vals if as_list else return_vals[0]

    def logbook_names(self):
        return self.configp.sections()


    @property
    def lb_attrs(self):
        return self._lb_attrs

    def IOptions(self, logbook: Logbook, lowercase=False):
        return [
            attr_name.lower() if lowercase else attr_name
            for attr_name, attr in self.lb_attrs[logbook.name].items()
            if attr.options_type == "IOptions"
        ]

    def Required(self, logbook: Logbook, lowercase=False):
        return [
            attr_name.lower() if lowercase else attr_name
            for attr_name, attr in self.lb_attrs[logbook.name].items()
            if attr.required
        ]

def active_config(cls) -> LogbookConfig:
    if cls._active_config is None:
        cls.reload_config()
    return cls._active_config


def config_updated(sender, **kwargs):
    global _cfg
    reload_config()


def logbook_updated(sender, **kwargs):
    logbook = kwargs['instance']
    created = kwargs['created']
    raw = kwargs['raw']
    if created and not raw and logbook.auth_required:
        # Create default groups for the logbook management
        for group_name, group_perms in settings.DEFAULT_LOGBOOK_GROUP_PERMISSIONS.items():
            group, was_created = Group.objects.get_or_create(name=group_name.format(logbook=logbook))
            if was_created:  # don't add permissions if group already existed
                for perm in group_perms:
                    assign_perm(perm, group, logbook)

    reload_config()


def reload_config():
    global _cfg
    try:
        global_config_text = "[global]\n" + ElogConfig.objects.get(name="global").config_text + "\n"
    except ElogConfig.DoesNotExist:
        global_config_text = "[global]\n"
    lb_config_texts = [f"\n\n[{lb.name}]\n" + (lb.config if lb.config else "\n") for lb in Logbook.active_logbooks()]
    _cfg = LogbookConfig(global_config_text + "".join(lb_config_texts))

# Set up signal to reload config if ElogConfig changed
post_save.connect(config_updated, sender=ElogConfig)
post_save.connect(logbook_updated, sender=Logbook)

def get_config() -> LogbookConfig:
    global _cfg
    if _cfg is None:
        reload_config()
    return _cfg

def cfg_context(request):
    return {
        "cfg": _cfg
    }