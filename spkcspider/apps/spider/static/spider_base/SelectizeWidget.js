
document.addEventListener("DOMContentLoaded", function(){
  $(".SelectizeWidgetTarget").selectize({
    create: false,
    delimiter: null,
    plugins: {
      'remove_button': {}
    }
  });
})
