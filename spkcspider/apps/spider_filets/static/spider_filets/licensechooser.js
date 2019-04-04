
document.addEventListener("DOMContentLoaded", function(){
  let el = document.getElementById("id_license_name")
  let target = document.getElementById("id_license_wrapper")
  let initial_value = target.style.display;
  if(el.value != "other"){
    target.style.display = "none";
  }
  el.addEventListener("change", function(event){
    if(event.target.value == "other"){
      target.style.display = "none";
    } else {
      target.style.display = initial_value;
    }
  })
})
