// src/main.js

// Import the Crepe editor (Vite resolves this from node_modules)
import { Crepe } from '@milkdown/crepe';

// Corrected CSS Import Paths:
import '@milkdown/crepe/theme/common/style.css';

// Import your chosen Crepe theme's styles (e.g., frame theme)
import '@milkdown/crepe/theme/frame.css';

// You could also import other specific plugin styles if needed, e.g.:
// import '@milkdown/plugin-menu/lib/style.css';
// import '@milkdown/plugin-table/lib/style.css';


// Define initial Markdown content
const initialMarkdown = `
# Welcome to Crepe! 🥞 (Local Version)

This Milkdown Crepe editor is running from your **local \`node_modules\`** using **Vite**.

## Features:

* **Rich Text Editing**: Bold, italic, strikethrough, etc.
* **Headings**: H1 to H6.
* **Lists**: Bulleted and numbered lists.
* **Code Blocks**: With syntax highlighting.
    \`\`\`javascript
    function helloLocalCrepe() {
        console.log("Hello from local Crepe editor!");
    }
    helloLocalCrepe();
    \`\`\`
* **Blockquotes**:
    > "The best way to predict the future is to create it." - Peter Drucker
* **Links**: [Milkdown GitHub Repo](https://github.com/Milkdown/milkdown)
* **Images**: ![Vite Logo](https://vitejs.dev/logo.svg "Vite Logo")

---

Start typing to explore!
`;

async function initializeCrepeEditor() {
    const crepe = new Crepe({
        root: document.getElementById('editor-container'),
        defaultValue: initialMarkdown,
        // You can configure specific features here:
        // features: {
        //     [Crepe.Feature.CodeMirror]: true,
        //     [Crepe.Feature.Toolbar]: true,
        //     [Crepe.Feature.Table]: true,
        // },
    });

    try {
        await crepe.create();
        console.log('Milkdown Crepe editor (local) has been initialized successfully!');

        // Optional: Get markdown content on change
        crepe.on((listener) => {
            listener.markdownUpdated((markdown) => {
                console.log("Markdown updated:", markdown);
            });
        });

    } catch (error) {
        console.error('Failed to initialize Milkdown Crepe editor:', error);
    }
}

// Call the initialization function
initializeCrepeEditor();