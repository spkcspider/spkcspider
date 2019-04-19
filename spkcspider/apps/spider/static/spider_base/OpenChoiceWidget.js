
document.addEventListener("DOMContentLoaded", function(){
  $(".OpenChoiceTarget").select2({
    tags: true,
    width: 'element',
    language: document.documentElement.lang || "en",
  });
})
