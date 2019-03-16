
JSONEditor.plugins.select2.enable = true;
document.addEventListener("DOMContentLoaded", function(){
  let collection = document.getElementsByClassName("SchemeEditorTarget");
  for (let counter=0;counter<collection.length;counter++){
    let element = collection[counter];
    let field_types = []
    try{
      field_types = JSON.parse(element.attributes.field_types.value);
    } catch(e){
      console.log(e);
    }
    let validator_editor = new JSONEditor(document.getElementById(`${element.id}_inner_wrapper`), {
      theme: 'html',
      iconlib: 'fontawesome5',
      compact: true,
      disable_collapse: true,
      schema: {
        "type": "array",
        "title": "Schema",
        "format": "tabs",
        "disable_properties": false,
        "items": {
          "title": "Field",
          "type": "object",
          "remove_empty_properties": true,
          "headerTemplate": "{{ self.key }}",
          "properties": {
            "key": {
              "title": "Name of the field",
              "type": "string"
            },
            "label": {
              "title": "Field label",
              "type": "string"
            },
            "nonhashable": {
              "title": "Exclude from verification",
              "type": "boolean",
              "format": "checkbox"
            },
            "help_text": {
              "title": "Field help text",
              "type": "string"
            },
            "field": {
              "title": "Field type",
              "type": "string",
              "enum": field_types
            }
          }
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
