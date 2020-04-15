
document.addEventListener("DOMContentLoaded", function(){
  for (let element of document.getElementsByClassName("SelectizeWidgetTarget")) {
    new Choices(element, {
      addItems: false,
      removeItems: false,
      delimiter: null,
      duplicateItemsAllowed: false
    });
  }
})
