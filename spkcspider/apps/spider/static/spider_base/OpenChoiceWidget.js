
document.addEventListener("DOMContentLoaded", function(){
  for (let element of document.getElementsByClassName("SelectizeWidgetTarget")) {
    new Choices(element, {
      addItems: true,
      removeItems: true,
      removeItemButton: true,
      delimiter: null,
      duplicateItemsAllowed: false
    });
  }
})
