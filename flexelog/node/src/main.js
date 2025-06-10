// src/main.js

// Import the Crepe editor
import { Crepe } from '@milkdown/crepe';

// Import Crepe's essential common styles
import '@milkdown/crepe/theme/common/style.css';

// Import your chosen Crepe theme's styles (e.g., frame theme)
import '@milkdown/crepe/theme/frame.css';

// --- No need to import markdown-it anymore as we're showing raw markdown ---
// import MarkdownIt from 'markdown-it';
// const md = new MarkdownIt(...); // Remove this line

// Define initial Markdown content
const initialMarkdown = `
# Welcome to Crepe! 🥞 (WYSIWYG & Source)

This **Milkdown Crepe editor** allows you to edit in the left panel and see the raw Markdown source on the right.

## How it works:

1.  Type and format text in the **WYSIWYG editor (left)**.
    * **Select text** to reveal the formatting toolbar.
    * Type \`/\` on a new line for **slash commands**.
2.  The **Raw Markdown Source (right)** panel updates instantly.

### Code Blocks
\`\`\`javascript
function greetings() {
  console.log("Hello, Markdown!");
}
greetings();
\`\`\`

### Tables
| WYSIWYG Editor | Raw Markdown |
|----------------|--------------|
| Live Editing   | Source View  |
| Toolbar        | Syncs Automatically |

---

Start typing to see the magic!
`;

async function initializeCrepeEditor() {
    // Get reference to the raw markdown output element
    const rawMarkdownOutputElement = document.getElementById('markdown-output-raw');

    const crepe = new Crepe({
        root: document.getElementById('editor-container'),
        defaultValue: initialMarkdown,
        // --- ENSURE THESE FEATURES ARE ENABLED FOR THE TOOLBAR ---
        features: {
            [Crepe.Feature.Toolbar]: true,       // Enables the floating toolbar for text formatting
            [Crepe.Feature.LinkTooltip]: true,   // Enables the tooltip when clicking on links
            [Crepe.Feature.TableTooltip]: true,  // Enables table-specific toolbar when inside a table
            [Crepe.Feature.ImageTooltip]: true,  // Enables image-specific toolbar when on an image
            [Crepe.Feature.CodeBlockTooltip]: true, // Optional: tooltip for code blocks
            [Crepe.Feature.Slash]: true,         // Optional: Enables slash commands (type '/')
            // [Crepe.Feature.History]: true,       // Optional: for undo/redo
        },
        // --------------------------------------------------------
    });

    try {
        await crepe.create();
        console.log('Milkdown Crepe editor (local) has been initialized successfully!');

        // Initial display of raw Markdown
        rawMarkdownOutputElement.textContent = initialMarkdown;

        // Listen for markdown updates
        crepe.on((listener) => {
            listener.markdownUpdated((markdown) => {
                // Directly set the textContent of the raw output element
                rawMarkdownOutputElement.textContent = markdown;
                console.log("Markdown updated in raw source panel.");
            });
        });

    } catch (error) {
        console.error('Failed to initialize Milkdown Crepe editor:', error);
    }
}

// Call the initialization function
initializeCrepeEditor();