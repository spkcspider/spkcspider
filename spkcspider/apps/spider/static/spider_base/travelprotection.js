

jQuery.noConflict();
var travel_protection_initialized = false;

jQuery( document ).ready(function( $ ) {
  if (travel_protection_initialized)
    return;
  travel_protection_initialized = true;
  if(document.getElementById("id_self_protection").value != "pw"){
    $("#id_new_pw_wrapper").hide();
    $("#id_new_pw2_wrapper").hide();
  }
  if(document.getElementById("id_self_protection").value != "token"){
    $("#id_token_arg_wrapper").hide();
    $("#id_token_arg_wrapper").hide();
  }
  $("#id_self_protection").on("change", function (event){
    if(event.target.value == "pw"){
      $("#id_new_pw_wrapper").show();
      $("#id_new_pw2_wrapper").show();
    } else {
      $("#id_new_pw_wrapper").hide();
      $("#id_new_pw2_wrapper").hide();
    }
    if(event.target.value == "token"){
      $("#id_token_arg_wrapper").show();
    }else {
      $("#id_token_arg_wrapper").hide();
    }
  })
})
