
jQuery.noConflict();
var open_choice_initialized = false;

jQuery( document ).ready(function( $ ) {
  if (open_choice_initialized)
    return;
  open_choice_initialized = true;
  $(".OpenChoice").select2({
    tags: true,
    width: 'element'
  });
})
