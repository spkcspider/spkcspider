

document.addEventListener("DOMContentLoaded", function(){
  let source_element = $("#id_text");
  let dest_element = document.getElementById("id_content_control-description");
  let modify_dest = false;
  if (dest_element.value == ""){
    modify_dest = true;
    dest_element.value = source_element.html().replace(/<\/?[^>]+(>|$)/g, " ").replace(/\ +/g, " ").trim().substr(0,500);
  }
  dest_element.addEventListener("input", function(event){
    if(event.target.value==""){
      modify_dest = true;
      dest_element.value = source_element.html().replace(/<\/?[^>]+(>|$)/g, " ").replace(/\ +/g, " ").trim().substr(0,500);
    } else {
      modify_dest = false;
    }
  });
  source_element.on("tbwchange", function(event){
    if (modify_dest){
      dest_element.value = event.target.value.replace(/<\/?[^>]+(>|$)/g, " ").replace(/\ +/g, " ").trim().substr(0,500);
    }
  });
});
