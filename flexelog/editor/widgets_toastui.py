from django import forms
from django.templatetags.static import static

# Adapted from django-tuieditor (https://github.com/nhn/tui.editor)
# Changed to CDN rather than local scripts
# Ideally should use webpack or Vite, etc to collapse into single optimized js
common_css = {
    "screen": (
        "https://uicdn.toast.com/editor/latest/toastui-editor.min.css",
        "https://uicdn.toast.com/chart/latest/toastui-chart.min.css",
        "https://uicdn.toast.com/tui-color-picker/latest/tui-color-picker.min.css",
        "https://cdnjs.cloudflare.com/ajax/libs/prism/1.23.0/themes/prism.min.css",
        "https://uicdn.toast.com/editor-plugin-color-syntax/latest/toastui-editor-plugin-color-syntax.min.css",
        "https://uicdn.toast.com/editor-plugin-code-syntax-highlight/latest/toastui-editor-plugin-code-syntax-highlight.min.css",
        "https://uicdn.toast.com/editor-plugin-table-merged-cell/latest/toastui-editor-plugin-table-merged-cell.min.css",
        "https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css",  
    ),  
}


common_js = (
    "https://uicdn.toast.com/chart/latest/toastui-chart.min.js",
    "https://uicdn.toast.com/tui-color-picker/latest/tui-color-picker.min.js",
    "https://uicdn.toast.com/editor/latest/toastui-editor-all.min.js",
    "https://uicdn.toast.com/editor-plugin-chart/latest/toastui-editor-plugin-chart.min.js",
    "https://uicdn.toast.com/editor-plugin-code-syntax-highlight/latest/toastui-editor-plugin-code-syntax-highlight-all.min.js",
    "https://uicdn.toast.com/editor-plugin-color-syntax/latest/toastui-editor-plugin-color-syntax.min.js",
    "https://uicdn.toast.com/editor-plugin-table-merged-cell/latest/toastui-editor-plugin-table-merged-cell.min.js",
    "https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js",   
    static("flexelog/toastui-local.js"),
)


class MarkdownEditorWidget(forms.Textarea):
    template_name = 'flexelog/editor/editor-toastui.html'

    class Media:
        css = common_css
        js = common_js

    def __init__(self, attrs=None):
        default_attrs = {'hidden': True}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class MarkdownViewerWidget(forms.Textarea):
    template_name = 'flexelog/editor/viewer-toastui.html'

    def __init__(self, attrs=None):
        default_attrs = {'class': 'tui-editor-contents', 'hidden': True}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    class Media:
        css = common_css
        js = common_js
