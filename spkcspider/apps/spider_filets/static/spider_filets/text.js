
jQuery.noConflict();
var trumbowyg_initialized = false;

jQuery( document ).ready(function( $ ) {
  if (trumbowyg_initialized)
    return;
  trumbowyg_initialized = true;
  $('#id_text').trumbowyg({
    btns: [
        ['viewHTML'],
        ['historyUndo', 'historyRedo'], // Only supported in Blink browsers
        ['formatting'],
        ['strong', 'em', 'del'],
        ['superscript', 'subscript'],
        ['link'],
        ['insertImage', 'base64'],
        ['foreColor', 'backColor'],
        ['justifyLeft', 'justifyCenter', 'justifyRight', 'justifyFull'],
        ['unorderedList', 'orderedList'],
        ['horizontalRule'],
        ['removeformat'],
        ['fullscreen']
    ]
  });
});
