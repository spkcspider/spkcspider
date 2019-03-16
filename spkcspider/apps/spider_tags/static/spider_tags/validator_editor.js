
document.addEventListener("DOMContentLoaded", function(){
  let collection = document.getElementsByClassName("ValidatorTarget");
  for (let counter=0;counter<collection.length;counter++){
    let element = collection[counter];
    let validator_editor = new JSONEditor(document.getElementById(`${element.id}_inner_wrapper`), {
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
          "type": "string",
          "format": "url"
        }
      }
    });
    element.style.display = 'none';
    validator_editor.setValue(JSON.parse(element.value));
    let handler = function (ev){
      let errors = validator_editor.validate();
      if (errors.length){
        ev.preventDefault();
      } else {
        element.value = JSON.stringify(validator_editor.getValue());
      }
    };
    element.form.addEventListener("submit", handler, false);
  }
}, false);
