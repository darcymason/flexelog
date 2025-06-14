function latexPlugin() {
    const toHTMLRenderers = {
        latex(node) {
            const html = katex.renderToString(node.literal);

            return [
                { type: 'openTag', tagName: 'div', outerNewLine: true },
                { type: 'html', content: html },
                { type: 'closeTag', tagName: 'div', outerNewLine: true }
            ];
        }
    }
    return { toHTMLRenderers };
}

const { Editor } = toastui;
const { chart, codeSyntaxHighlight, colorSyntax, tableMergedCell } = Editor.plugin;