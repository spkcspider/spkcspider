
jQuery.noConflict();
var select2_multiple_initialized = false;

jQuery( document ).ready(function( $ ) {
  if (select2_multiple_initialized)
    return;
  select2_multiple_initialized = true;
  $(".Select2Target").select2();
})
