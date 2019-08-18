
document.addEventListener("DOMContentLoaded", function(){
  let required_passes_counter = 0;
  let required_passes_html = document.getElementById("id_required_passes");
  let checked_handler = function(event){
    let element = event.target;
    let val;
    let target_val;
    if(element.value == "b" && element.checked){
      val = 1;
    } else {
      val = -1;
    }
    target_val = Number(required_passes_html.value);
    if (target_val == Math.max(required_passes_counter, 0)){
      required_passes_counter = required_passes_counter+val;
      required_passes_html.value = required_passes_counter;
    } else {
      required_passes_counter = required_passes_counter+val;
    }
    // should not propagate
    return false;
  }

  // update-required_passes classes consist of instant_fail and active
  for (let element of document.getElementsByClassName("update-required_passes")){
    if(element.type != "radio"){
      // parent
      element.addEventListener("change", checked_handler);
    } else if(element.value == "b" && element.checked){
      // radio child
      required_passes_counter+=1;
    }
  }
})
