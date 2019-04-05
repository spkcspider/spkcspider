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
    editor.setValue(JSON.parse(element.value));
    let handler = function (ev){
      let errors = editor.validate();
      if (errors.length){
        ev.preventDefault();
      } else {
        element.value = JSON.stringify(editor.getValue());
      }
    };
    element.form.addEventListener("submit", handler, false);

  }
})
