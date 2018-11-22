
jQuery.noConflict();
var trumbowyg_initialized = false;

jQuery( document ).ready(function( $ ) {
  if (trumbowyg_initialized)
    return;
  trumbowyg_initialized = true;
  $('#id_content').trumbowyg({
    btnsDef: {
        // Create a new dropdown
        image: {
            dropdown: ['insertImage', 'base64'],
            ico: 'insertImage'
        }
    },
    btns: [
        ['viewHTML'],
        ['historyUndo', 'historyRedo'], // Only supported in Blink browsers
        ['formatting'],
        ['strong', 'em', 'del'],
        ['superscript', 'subscript'],
        ['link'],
        ['image'],
        ['foreColor', 'backColor'],
        ['justifyLeft', 'justifyCenter', 'justifyRight', 'justifyFull'],
        ['unorderedList', 'orderedList'],
        ['horizontalRule'],
        ['removeformat'],
        ['fullscreen']
    ]
  });
});
