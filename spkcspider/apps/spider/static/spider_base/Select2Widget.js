
document.addEventListener("DOMContentLoaded", function(){
  $(".Select2WidgetTarget").select2(
    {
      width: 'element',
      language: document.documentElement.lang || "en",
    }
  );
})
