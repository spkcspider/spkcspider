
jQuery.noConflict();
var trumbowygwidget_initialized = false;

jQuery( document ).ready(function( $ ) {
  if (trumbowygwidget_initialized)
    return;
  trumbowygwidget_initialized = true;
  $('.TrumbowygTarget').trumbowyg({
    resetCss: true,
    autogrowOnEnter: true,
    imageWidthModalEdit: true,
    minimalLinks: true,
    btnsDef: {
        // Create a new dropdown
        insert: {
            dropdown: ['insertImage', 'base64', 'insertaudio'],
            ico: 'insertImage'
        },
        justify: {
            dropdown: ['justifyLeft', 'justifyCenter', 'justifyRight', 'justifyFull'],
            ico: 'justifyFull'
        }
    },
    btns: [
        ['viewHTML'],
        ['historyUndo', 'historyRedo'], // Only supported in Blink browsers
        ['formatting', 'preformatted'],
        ['strong', 'em', 'del'],
        ['superscript', 'subscript'],
        ['foreColor', 'backColor'],
        ['justify'],
        ['horizontalRule', 'table'],
        ['link', 'insert', 'emoji'],
        ['unorderedList', 'orderedList'],
        ['removeformat'],
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
