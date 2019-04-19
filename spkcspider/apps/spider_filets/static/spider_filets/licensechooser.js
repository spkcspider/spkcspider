
document.addEventListener("DOMContentLoaded", function(){
  let el = document.getElementById("id_license_name");
  let license_urls = {}
  try{
    license_urls = JSON.parse(el.attributes.license_urls.value);
  } catch(e){
    console.log(e);
  }
  let target = document.getElementById("id_license_url");
  if(el.value in license_urls){
    try{
      target.value = license_urls[el.value];
    } catch(e){
      console.log(e);
    }
  }
  el.addEventListener("change", function(event){
    if(event.target.value in license_urls){
      try{
        target.value = license_urls[event.target.value];
      } catch(e){
        console.log(e);
      }
    }
  })
})
