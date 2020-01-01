document.addEventListener("DOMContentLoaded", function(){
  for (let element of document.getElementsByClassName("SpiderListTarget")){

    let items;
    try {
      items = JSON.parse(element.dataset.items);
    } catch (e) {
      console.log(e);
      continue
    }
    let orig_val = [];
    if (items["type"] !== "object"){
      for (let count=0; count < element.options.length; count++)
      {
        if (element.options[count].hasAttribute("selected")){
          orig_val.push(element.options[count].value)
        }
      }
    } else {
      for (let count = 0; count < element.options.length; count++) {
        if (element.options[count].hasAttribute("selected")) {
          orig_val.push(JSON.parse(element.options[count].value))
        }
      }
    }
    let editor = new JSONEditor(document.getElementById(`${element.id}_inner_wrapper`), {
      theme: 'html',
      iconlib: 'fontawesome5',
      disable_collapse: true,
      startval: orig_val,
      form_name_root:"",
      schema: {
        "type": "array",
        "options": {
          "compact": true,
        },
        "uniqueItems": true,
        "items": items
      }
    });
    element.style.display = "none";
    let handler = function (ev){
      let errors = editor.validate();
      if (errors.length){
        ev.preventDefault();
      } else {
        let editor_val = editor.getValue();
        while(element.options.length != 0) {
          element.options.remove(0);
        }
        for (let count=0; count < editor_val.length; count++)
        {
          let option = document.createElement("option");
          option.selected = true;
          option.value = editor_val[count];
          option.innerText = editor_val[count];
          element.options.add(option);
        }
      }
    };
    element.form.addEventListener("submit", handler, false);

  }
})
