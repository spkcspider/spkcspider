
let $ = jQuery.noConflict();

document.addEventListener("DOMContentLoaded", function(){
  $(".OpenChoiceTarget").select2({
    tags: true,
    width: 'element'
  });
})
