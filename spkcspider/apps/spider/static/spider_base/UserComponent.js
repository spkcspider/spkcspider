
document.addEventListener("DOMContentLoaded", function(){
  let required_passes_counter = 0;
  let required_passes_html = document.getElementById("id_required_passes");
  let checked_handler = function(event){
    let element = event.target;
    let val;
    let val2;
    if(element.checked){
      val = element.dataset.required_passes_val;
    } else {
      val = -element.dataset.required_passes_val;
    }
    val = Number(val);
    /**if (element.disable_instant_fail){
    *  element.disable_instant_fail.checked = false;
    * }
    */
    val2 = Number(required_passes_html.value);
    if (val2 == Math.max(required_passes_counter, 0)){
      required_passes_html.value = Math.max(val2 + val);
    }
    required_passes_counter = required_passes_counter+val;
    return true;
  }

  // update-required_passes classes consist of instant_fail and active
  let collection = document.getElementsByClassName("update-required_passes");
  for (let counter=0;counter<collection.length;counter++){
    let element = collection[counter];
    if(element.checked){
      required_passes_counter+=Number(element.dataset.required_passes_val);
    }
    element.addEventListener("change", checked_handler);
  }
})
