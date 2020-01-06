
document.addEventListener("DOMContentLoaded", function(){
  let required_passes_html = document.getElementById("id_required_passes");

  let checked_handler = function(event){
    let required_passes_counter = 0;
    let target_val;
    let element = event.target;
    for (let el of document.getElementsByClassName("update-required_passes")) {
      if (el.type == "radio" && el.value == "b" && el.checked) {
        // radio child
        required_passes_counter += 1;
      }
    }
    target_val = Number(required_passes_html.value);
    if ((target_val == required_passes_counter - 1 && element.type == "radio" && element.value == "b") || (target_val == required_passes_counter + 1 && element.type == "radio" && element.value != "b" )){
      required_passes_html.value = required_passes_counter;
    }
    // should not propagate
    return false;
  }

  // update-required_passes classes consist of instant_fail and active
  for (let element of document.getElementsByClassName("update-required_passes")){
    if(element.type != "radio"){
      // parent
      element.dataset.lastselected = element.value;
      element.addEventListener("change", checked_handler);
    }
  }
})
