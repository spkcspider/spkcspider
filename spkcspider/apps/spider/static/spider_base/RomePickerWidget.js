


document.addEventListener("DOMContentLoaded", function(){
  let collection = document.getElementsByClassName("RomeDatetimeTarget");
  for (let counter=0;counter<collection.length;counter++){
    let element = collection[counter];
    let rpicker = rome(element, {
      "autoClose": true,
      "autoHideOnBlur": true,
      "autoHideOnClick": true,
      "date": true,
      "time": true
    });
  }
})
