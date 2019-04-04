
document.addEventListener("DOMContentLoaded", function(){
  let el = document.getElementById("id_license_name");
  let licenses = {}
  try{
    licenses = JSON.parse(el.attributes.licenses.value);
  } catch(e){
    console.log(e);
  }
  let target = document.getElementById("id_license");
  if(el.value != "other"){
    target.disabled = true;
  }
  el.addEventListener("change", function(event){
    if(event.target.value == "other"){
      target.disabled = false;
    } else {
      target.disabled = true;
      try{
        target.value = licenses[event.target.value];
      } catch(e){
        console.log(e);
      }
    }
  })
})
