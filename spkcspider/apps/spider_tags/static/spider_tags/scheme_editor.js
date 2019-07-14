
/* JSONEditor.plugins.selectize.enable = true; */

document.addEventListener("DOMContentLoaded", function(){
  let collection = document.getElementsByClassName("SchemeEditorTarget");
  for (let counter=0;counter<collection.length;counter++){
    let element = collection[counter];
    let field_types = [];
    try{
      field_types = JSON.parse(element.dataset.field_types);
    } catch(e){
      console.log(e);
    }
    let scheme_editor = new JSONEditor(document.getElementById(`${element.id}_inner_wrapper`), {
      theme: 'html',
      iconlib: 'fontawesome5',
      disable_collapse: true,
      keep_oneof_values: false,
      startval: JSON.parse(element.value),
      form_name_root:"",
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
                      "type": "string",
                      "options": {
                        "inputAttributes": {
                          "form": "_dump_form"
                        }
                      }
                    },
                    "label": {
                      "title": "Sub Form Label",
                      "type": "string",
                      "options": {
                        "inputAttributes": {
                          "form": "_dump_form"
                        }
                      }
                    },
                    "field": {
                      "title": "Sub Array",
                      "$ref": "#/definitions/fieldarray",
                      "options": {
                        "inputAttributes": {
                          "form": "_dump_form"
                        }
                      }
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
                "type": "string",
                "options": {
                  "inputAttributes": {
                    "form": "_dump_form"
                  }
                }
              },
              "label": {
                "title": "Field label",
                "type": "string",
                "options": {
                  "inputAttributes": {
                    "form": "_dump_form"
                  }
                }
              },
              "required": {
                "title": "Required",
                "type": "boolean",
                "format": "checkbox",
                "options": {
                  "inputAttributes": {
                    "form": "_dump_form"
                  }
                }
              },
              "nonhashable": {
                "title": "Exclude from verification",
                "type": "boolean",
                "format": "checkbox",
                "options": {
                  "inputAttributes": {
                    "form": "_dump_form"
                  }
                }
              },
              "help_text": {
                "title": "Field help text",
                "type": "string",
                "options": {
                  "inputAttributes": {
                    "form": "_dump_form"
                  }
                }
              },
              "field": {
                "title": "Field type",
                "type": "string",
                "enum": field_types,
                "options": {
                  "inputAttributes": {
                    "form": "_dump_form"
                  }
                }
              }
            }
          }
        }
      }
    });
    element.style.display = 'none';
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
