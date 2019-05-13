
document.addEventListener("DOMContentLoaded", function(){
  $('.TrumbowygTarget').trumbowyg({
    imageWidthModalEdit: true,
    resetCss:true,
    minimalLinks: true,
    autogrow: false,
    urlProtocol: true,
    lang: document.documentElement.lang || "en",
    btnsDef: {
        // Create a new dropdown
        insert: {
            dropdown: ['insertImage', 'base64', 'insertAudio'],
            ico: 'insertImage'
        },
        justify: {
            dropdown: ['justifyLeft', 'justifyCenter', 'justifyRight', 'justifyFull'],
            ico: 'justifyFull'
        },
        formatting: {
            dropdown: ['p', 'preformatted', 'blockquote', 'h1', 'h2', 'h3', 'h4'],
            ico: 'p'
        },
        textmarkup: {
            dropdown: ['strong', 'em', 'del', 'superscript', 'subscript'],
            ico: 'strong'
        },
        lists: {
            dropdown: ['unorderedList', 'orderedList'],
            ico: 'unorderedList'
        }
    },
    btns: [
        ['viewHTML'],
        ['historyUndo', 'historyRedo'],
        ['formatting', 'textmarkup', 'foreColor', 'backColor', 'removeformat'],
        ['emoji', 'link', 'insert'],
        ['justify'],
        ['table','horizontalRule'],
        ['lists', 'lineheight'],
        ['fullscreen']
    ],
    plugins: {
      table: {
        rows: 12,
        columns: 10
      },
    }
  });
});
