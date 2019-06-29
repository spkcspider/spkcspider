
let getKeyForPw = function(pw,salt){
  let tencoder = new TextEncoder();
  return window.crypto.subtle.importKey(
    "raw",
    tencoder.encode(pw),
    {name: "PBKDF2"},
    false,
    ["deriveBits", "deriveKey"]
  ).then(function(pwkey){
    return window.crypto.subtle.deriveKey(
      {
        "name": "PBKDF2",
        "salt": tencoder.encode(salt),
        "iterations": 120000,
        "hash": "SHA-512"
      },
      pwkey,
      { "name": "AES-GCM", "length": 256},
      false,
      [ "encrypt", "decrypt" ]
    );
  });
}

let updatePWs = async function(pwfrom, pwto, salt){
  let tencoder = new TextEncoder();
  let tdecoder = new TextDecoder();
  let from_key = await getKeyForPw(pwfrom, salt);
  let to_key = await getKeyForPw(pwto, salt);
  let promises = [];
  let has_error=false;
  $(".PWProtectionTarget > option").each(function() {
    if (!this.selected){
      return;
    }
    let iv_val = this.value.split(":", 2);
    let opt = this;
    let _promise;
    if (iv_val.length === 1){
      _promise = Promise.resolve(tencoder.encode(iv_val[0]));
    } else if (iv_val[0] == "bogo"){
      _promise = Promise.resolve(tencoder.encode(iv_val[1]));
    } else {
      _promise = window.crypto.subtle.decrypt(
        {
          name: "AES-GCM",
          iv: base64js.toByteArray(iv_val[0])
        },
        from_key,
        base64js.toByteArray(iv_val[1])
      );
    }
    promises.push(_promise.then(
      function(result){
        let new_iv = window.crypto.getRandomValues(new Uint8Array(16));
        opt.text = tdecoder.decode(result);
        return window.crypto.subtle.encrypt(
          {
            name: "AES-GCM",
            iv: new_iv
          },
          to_key,
          result
        ).then(
          function(result2){
            let oldval=opt.value;
            opt.value = `${base64js.fromByteArray(new_iv)}:${base64js.fromByteArray(new Uint8Array(result2))}`;
            opt.parentElement.selectize.updateOption(
              oldval,
              {
                text: opt.text,
                value: opt.value
              }
            );
            return Promise.resolve();
          },
          function(error2){
            console.error(`encryption error:  salt: ${salt}, iv: ${new_iv[0]}, pw: ${tdecoder.decode(result)}: ${error2}`);
            has_error=true;
            return Promise.resolve();
          }
        )
      },
      function(error){
        console.error(`decryption error: salt: ${salt}, iv: ${iv_val[0]}, pw: ${iv_val[1]}: ${error}`);
        has_error=true;
        return Promise.resolve();
      }
    ));
  });
  await Promise.all(promises);
  return !has_error;
}


document.addEventListener("DOMContentLoaded", async function(){
  /* for encode/decoding */
  let tencoder = new TextEncoder();
  let tdecoder = new TextDecoder();
  let selectizers = null;
  let some_succeeded = false;
  let block_submits = true;
  let promises = [];
  let master_pw = document.getElementById("id_master_pw");
  let active = document.getElementById("id_protections_password-active");
  let default_master_pw = document.getElementById("id_protections_password-default_master_pw").value;
  let salt = document.getElementById("id_protections_password-salt").value;
  let last_pw;
  let effective_pw = default_master_pw;
  if (master_pw.value != ""){
    effective_pw = master_pw.value;
  }
  let submit_block_handler = function (ev){
    if (block_submits && active.checked){
      ev.preventDefault();
      ev.stopPropagation();
    }
  };
  master_pw.form.addEventListener("submit", submit_block_handler, false);

  let init_key = await getKeyForPw(effective_pw, salt);
  $(".PWProtectionTarget > option").each(function() {
    let iv_val = this.value.split(":", 2);
    let opt = this;
    let _promise;
    if (iv_val.length == 2){
      if (iv_val[0] == "bogo"){
        _promise = Promise.resolve(tencoder.encode(iv_val[1]));
      } else {
        _promise = window.crypto.subtle.decrypt(
          {
            name: "AES-GCM",
            iv: base64js.toByteArray(iv_val[0])
          },
          init_key,
          base64js.toByteArray(iv_val[1])
        );
      }
      promises.push(
        _promise.then(
          function(result){
            some_succeeded = true;
            opt.text = tdecoder.decode(result);
            return Promise.resolve();
          },
          function(error){
            all_succeeded = false;
            opt.text = iv_val[1];
            return Promise.resolve();
          }
        )
      );
    } else {
      console.warn(`Invalid value: ${iv_val}`)
    }
  });
  await Promise.all(promises);
  /* unlock after initialization complete */
  block_submits = false;
  selectizers = $(".PWProtectionTarget").selectize({
    delimiter: null,
    plugins: {
      'remove_button': {}
    },
    create: function (input) {
      let term = $.trim(input);
      all_succeeded = false;
      return {
        "value": `bogo:${term}`,
        "text": term
      };
    }
  });

  let change_master_pw_handler = async function (event){
    let effective_pw = default_master_pw;
    if (event.target.value != ""){
      effective_pw = event.target.value;
    }
    block_submits=true;
    selectizers.each(function(){this.selectize.lock()});
    if (some_succeeded){
      await updatePWs(last_pw, effective_pw, salt);
    } else {
      if (await updatePWs(effective_pw, effective_pw, salt)){
        some_succeeded = true;
      }
    }
    last_pw = effective_pw;
    selectizers.each(function(){this.selectize.unlock()});
    block_submits=false;
  }

  master_pw.addEventListener("change", change_master_pw_handler, false);
  $(".PWProtectionTarget").on('change', function (event){
    /* fix missing compatibility to async by triggering events*/
    master_pw.dispatchEvent(new CustomEvent("change"));
    return true;
  });

})
