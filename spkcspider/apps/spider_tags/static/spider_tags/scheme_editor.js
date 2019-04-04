
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
    let scheme_editor = new JSONEditor(document.getElementById(`${element.id}_inner_wrapper`), {
      theme: 'html',
      iconlib: 'fontawesome5',
      disable_collapse: true,
      schema: {
        "title": "Schema",
        "$ref": "#/definitions/fieldarray",
        "definitions": {
          "fieldarray": {
            "type": "array",
            "title": "Field Array",
            "id": "fieldarray",
            "format": "tabs",
            "items": {
              "title": "Entry",
              "oneOf": [
                {
                  "title": "Field",
                  "$ref": "#/definitions/field"
                },
                {
                  "title": "Sub Form",
                  "type": "object",
                  "disable_properties": true,
                  "no_additional_properties": true,
                  "disable_edit_json": true,
                  "properties": {
                    "key": {
                      "title": "Sub Form Key",
                      "type": "string"
                    },
                    "label": {
                      "title": "Sub Form Label",
                      "type": "string"
                    },
                    "field": {
                      "title": "Sub Array",
                      "$ref": "#/definitions/fieldarray"
                    }
                  }
                }
              ]
            }
          },
          "field": {
            "type": "object",
            "title": "Field",
            "id": "field",
            "disable_properties": false,
            "remove_empty_properties": true,
            "properties": {
              "key": {
                "title": "Name of the field",
                "type": "string"
              },
              "label": {
                "title": "Field label",
                "type": "string"
              },
              "required": {
                "title": "Required",
                "type": "boolean",
                "format": "checkbox"
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
      }
    });
    element.style.display = 'none';
    scheme_editor.setValue(JSON.parse(element.value));
    let clean_handler = function (ev){
      /* if visible ignore */
      if (element.style.display !== 'none'){
        return;
      }
      let errors = scheme_editor.validate();
      if (errors.length){
        ev.preventDefault();
      } else {
        element.value = JSON.stringify(scheme_editor.getValue());
      }
    };
    let toggle_handler = function (ev){
      ev.preventDefault();
      ev.stopPropagation();
      if (element.style.display === 'none'){
        element.value = JSON.stringify(scheme_editor.getValue(), null, 4);
        scheme_editor.disable();
        element.style.display = 'block';
      } else {
        scheme_editor.enable();
        element.style.display = 'none';
      }
    };
    let editor = scheme_editor.getEditor('root')
    let togglebut = editor.getButton('raw','', null);
    togglebut.classList.add('json-editor-btntype-toggle');
    togglebut.addEventListener("click", toggle_handler, false);
    editor.controls.appendChild(togglebut);
    element.form.addEventListener("submit", clean_handler, false);
  }
}, false);
