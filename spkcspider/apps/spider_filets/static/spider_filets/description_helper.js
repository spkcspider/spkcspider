
let clean_description_text = function(inp){
  return inp.replace(/(?:<|&lt;)\/?.(?!&gt;|>)*.?(?:&gt;|>|$)/g, " ").replace(/\ +/g, " ").trim();
}

document.addEventListener("DOMContentLoaded", function(){
  let source_element = $("#id_text");
  let dest_element = document.getElementById("id_content_control-description");
  let modify_dest = false;
  /* last char will be replaced by …*/
  let max_length = dest_element.attributes.maxlength.value;
  let val = clean_description_text(source_element.html()).substr(0,max_length);
  if (dest_element.value == "" || dest_element.value.substr(0,max_length)==val){
    modify_dest = true;
    dest_element.value = val;
  }
  dest_element.addEventListener("input", function(event){
    val = clean_description_text(source_element.html()).substr(0,max_length);
    /* || dest_element.value.substr(0,500)==val*/
    if(event.target.value==""){
      modify_dest = true;
      dest_element.value = val
    } else {
      modify_dest = false;
    }
  });
  source_element.on("tbwchange", function(event){
    if (modify_dest){
      dest_element.value = clean_description_text(event.target.value).substr(0,max_length);
    }
  });
});
