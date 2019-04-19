
document.addEventListener("DOMContentLoaded", function(){
  let el = $("#id_license_name");
  let license_urls = {}
  try{
    license_urls = JSON.parse(el.attr("license_urls"));
  } catch(e){
    console.log(e);
  }
  let target = document.getElementById("id_license_url");
  if(el.val() in license_urls){
    try{
      target.value = license_urls[el.val()];
    } catch(e){
      console.log(e);
    }
  }
  el.on("change", function(event){
    if(event.target.value in license_urls){
      try{
        target.value = license_urls[event.target.value];
      } catch(e){
        console.log(e);
      }
    }
  })
})
