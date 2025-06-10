// src/main.js

// --- Removed Milkdown Crepe imports ---
// import { Crepe } from '@milkdown/crepe';
// import '@milkdown/crepe/theme/common/style.css';
// import '@milkdown/crepe/theme/frame.css';

// Import markdown-it for Markdown to HTML conversion
import MarkdownIt from 'markdown-it';


// Initialize markdown-it
const md = new MarkdownIt({
    html: true,       // Enable HTML tags in source
    linkify: true,    // Autoconvert URL-like text to links
    typographer: true // Enable some typographic replacements
});

// Define initial Markdown content
const initialMarkdown = `
# Hello, Split Editor!

Type **Markdown** on the left, see **rendered HTML** on the right.

---

## Features:

* **Real-time conversion**
* Supports common Markdown syntax:
    * *Italics*
    * **Bold**
    * \`Inline code\`
    * ~~Strikethrough~~

### Lists:

* Item 1
* Item 2
    1.  Sub-item A
    2.  Sub-item B

### Code Blocks:

\`\`\`javascript
function sayHello() {
  console.log('Hello from JS!');
}
sayHello();
\`\`\`

### Tables:

| Header 1 | Header 2 |
| -------- | -------- |
| Cell A   | Cell B   |
| Cell C   | Cell D   |

### Links and Images:

[Visit Google](https://www.google.com)
![Placeholder Image](https://via.placeholder.com/150 "A placeholder")
`;

function initializeSplitEditor() {
    const markdownInput = document.getElementById('markdown-input-raw');
    const htmlOutput = document.getElementById('html-output');

    // Set initial content
    markdownInput.value = initialMarkdown;
    htmlOutput.innerHTML = md.render(initialMarkdown);

    // Listen for input changes in the textarea
    markdownInput.addEventListener('input', () => {
        const markdown = markdownInput.value;
        htmlOutput.innerHTML = md.render(markdown);
    });

    console.log('Split Markdown editor initialized.');
}

// Call the initialization function when the DOM is ready
initializeSplitEditor();