
document.addEventListener("DOMContentLoaded", function(){
  let collection = document.getElementsByClassName("FiletSourcesEditorTarget");
  for (let counter=0;counter<collection.length;counter++){
    let element = collection[counter];
    let urllist_editor = new JSONEditor(document.getElementById(`${element.id}_inner_wrapper`), {
      theme: 'html',
      iconlib: 'fontawesome5',
      disable_collapse: true,
      compact: true,
      schema: {
        "type": "array",
        "title": "Validators",
        "format": "table",
        "uniqueItems": true,
        "items": {
          "title": "Url of Validator",
          "type": "string"
        }
      }
    });
    element.style.display = 'none';
    urllist_editor.setValue(JSON.parse(element.value));
    let handler = function (ev){
      let errors = urllist_editor.validate();
      if (errors.length){
        ev.preventDefault();
      } else {
        element.value = JSON.stringify(urllist_editor.getValue());
      }
    };
    element.form.addEventListener("submit", handler, false);
  }
}, false);
