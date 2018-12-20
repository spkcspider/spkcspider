
jQuery.noConflict();
var trumbowygwidget_initialized = false;

jQuery( document ).ready(function( $ ) {
  if (trumbowygwidget_initialized)
    return;
  trumbowygwidget_initialized = true;
  $('.TrumbowygTarget').trumbowyg({
    imageWidthModalEdit: true,
    resetCss:true,
    minimalLinks: true,
    urlProtocol: true,
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
        ['historyUndo', 'historyRedo'], // Only supported in Blink browsers
        ['formatting', 'textmarkup', 'foreColor', 'backColor', 'removeformat'],
        ['justify'],
        ['table','horizontalRule'],
        ['link', 'insert', 'emoji'],
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
