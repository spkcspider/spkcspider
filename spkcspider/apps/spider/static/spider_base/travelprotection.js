
document.addEventListener("DOMContentLoaded", function(){
  let self_protection = document.getElementById("id_self_protection");
  let token_wrapper = document.getElementById("id_token_arg_wrapper");
  let new_pw_wrapper = document.getElementById("id_new_pw_wrapper");
  let new_pw2_wrapper = document.getElementById("id_new_pw2_wrapper");
  if(self_protection.value != "pw"){
    new_pw_wrapper.style.display = "none";
    new_pw2_wrapper.style.display = "none";
  }
  if(self_protection.value != "token"){
    token_wrapper.style.display = "none";
  }
  self_protection.addEventListener("change", function (event){
    if(event.target.value == "pw"){
      new_pw_wrapper.style.display = "";
      new_pw2_wrapper.style.display = "";
    } else {
      new_pw_wrapper.style.display = "none";
      new_pw2_wrapper.style.display = "none";
    }
    if(event.target.value == "token"){
      token_wrapper.style.display = "";
    }else {
      token_wrapper.style.display = "none";
    }
  })
})
