


document.addEventListener("DOMContentLoaded", function(){
  let collection = document.getElementsByClassName("DatetimeTarget");
  for (let counter=0;counter<collection.length;counter++){
    let element = collection[counter];
    let rpicker = flatpickr(element, {
      enableTime: true,
      time_24hr: true,
      dateFormat: "Y-m-d H:i"
    });
  }
})
