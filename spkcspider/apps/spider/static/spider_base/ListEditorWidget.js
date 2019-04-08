document.addEventListener("DOMContentLoaded", function(){
  let collection = document.getElementsByClassName("SpiderListTarget");
  for (let counter=0;counter<collection.length;counter++){
    let element = collection[counter];
    let ftype = "text";
    let ilabel = "Item";
    try{
      ftype = element.attributes.format_type.value;
    } catch(e){
      console.log(e);
    }
    try{
      ilabel = element.attributes.item_label.value;
    } catch(e){
      console.log(e);
    }
    let editor = new JSONEditor(document.getElementById(`${element.id}_inner_wrapper`), {
      theme: 'html',
      iconlib: 'fontawesome5',
      disable_collapse: true,
      schema: {
        "type": "array",
        "options": {
          "compact": true
        },
        "format": "table",
        "uniqueItems": true,
        "items": {
          "title": ilabel,
          "type": "string",
          "format": ftype
        }
      }
    });
    element.style.display = "none";
    let orig_val = [];
    for (let count=0; count < element.options.length; count++)
    {
      if (element.options[count].hasAttribute("selected")){
        orig_val.push(element.options[count].value)
      }
    }
    editor.setValue(orig_val);
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
