// API 基础地址
var API_BASE_URL = 'https://api.hishutdown.cn/xqe2ics/subscribe/v2';

// MD5 转换函数
function md5(string) {
  function md5_RotateLeft(lValue, iShiftBits) {
    return (lValue << iShiftBits) | (lValue >>> (32 - iShiftBits));
  }
  function md5_AddUnsigned(lX, lY) {
    var lX4, lY4, lX8, lY8, lResult;
    lX8 = (lX & 0x80000000);
    lY8 = (lY & 0x80000000);
    lX4 = (lX & 0x40000000);
    lY4 = (lY & 0x40000000);
    lResult = (lX & 0x3FFFFFFF) + (lY & 0x3FFFFFFF);
    if (lX4 & lY4) {
      return (lResult ^ 0x80000000 ^ lX8 ^ lY8);
    }
    if (lX4 | lY4) {
      if (lResult & 0x40000000) {
        return (lResult ^ 0xC0000000 ^ lX8 ^ lY8);
      } else {
        return (lResult ^ 0x40000000 ^ lX8 ^ lY8);
      }
    } else {
      return (lResult ^ lX8 ^ lY8);
    }
  }
  function md5_F(x, y, z) { return (x & y) | ((~x) & z); }
  function md5_G(x, y, z) { return (x & z) | (y & (~z)); }
  function md5_H(x, y, z) { return (x ^ y ^ z); }
  function md5_I(x, y, z) { return (y ^ (x | (~z))); }
  function md5_FF(a, b, c, d, x, s, ac) {
    a = md5_AddUnsigned(a, md5_AddUnsigned(md5_AddUnsigned(md5_F(b, c, d), x), ac));
    return md5_AddUnsigned(md5_RotateLeft(a, s), b);
  }
  function md5_GG(a, b, c, d, x, s, ac) {
    a = md5_AddUnsigned(a, md5_AddUnsigned(md5_AddUnsigned(md5_G(b, c, d), x), ac));
    return md5_AddUnsigned(md5_RotateLeft(a, s), b);
  }
  function md5_HH(a, b, c, d, x, s, ac) {
    a = md5_AddUnsigned(a, md5_AddUnsigned(md5_AddUnsigned(md5_H(b, c, d), x), ac));
    return md5_AddUnsigned(md5_RotateLeft(a, s), b);
  }
  function md5_II(a, b, c, d, x, s, ac) {
    a = md5_AddUnsigned(a, md5_AddUnsigned(md5_AddUnsigned(md5_I(b, c, d), x), ac));
    return md5_AddUnsigned(md5_RotateLeft(a, s), b);
  }
  function md5_ConvertToWordArray(string) {
    var lWordCount;
    var lMessageLength = string.length;
    var lNumberOfWords_temp1 = lMessageLength + 8;
    var lNumberOfWords_temp2 = (lNumberOfWords_temp1 - (lNumberOfWords_temp1 % 64)) / 64;
    var lNumberOfWords = (lNumberOfWords_temp2 + 1) * 16;
    var lWordArray = Array(lNumberOfWords - 1);
    var lBytePosition = 0;
    var lByteCount = 0;
    while (lByteCount < lMessageLength) {
      lWordCount = (lByteCount - (lByteCount % 4)) / 4;
      lBytePosition = (lByteCount % 4) * 8;
      lWordArray[lWordCount] = (lWordArray[lWordCount] | (string.charCodeAt(lByteCount) << lBytePosition));
      lByteCount++;
    }
    lWordCount = (lByteCount - (lByteCount % 4)) / 4;
    lBytePosition = (lByteCount % 4) * 8;
    lWordArray[lWordCount] = lWordArray[lWordCount] | (0x80 << lBytePosition);
    lWordArray[lNumberOfWords - 2] = lMessageLength << 3;
    lWordArray[lNumberOfWords - 1] = lMessageLength >>> 29;
    return lWordArray;
  }
  function md5_WordToHex(lValue) {
    var WordToHexValue = "", WordToHexValue_temp = "", lByte, lCount;
    for (lCount = 0; lCount <= 3; lCount++) {
      lByte = (lValue >>> (lCount * 8)) & 255;
      WordToHexValue_temp = "0" + lByte.toString(16);
      WordToHexValue = WordToHexValue + WordToHexValue_temp.substr(WordToHexValue_temp.length - 2, 2);
    }
    return WordToHexValue;
  }
  var x = Array();
  var k, AA, BB, CC, DD, a, b, c, d;
  var S11 = 7, S12 = 12, S13 = 17, S14 = 22;
  var S21 = 5, S22 = 9, S23 = 14, S24 = 20;
  var S31 = 4, S32 = 11, S33 = 16, S34 = 23;
  var S41 = 6, S42 = 10, S43 = 15, S44 = 21;
  x = md5_ConvertToWordArray(string);
  a = 0x67452301; b = 0xEFCDAB89; c = 0x98BADCFE; d = 0x10325476;
  for (k = 0; k < x.length; k += 16) {
    AA = a; BB = b; CC = c; DD = d;
    a = md5_FF(a, b, c, d, x[k + 0], S11, 0xD76AA478);
    d = md5_FF(d, a, b, c, x[k + 1], S12, 0xE8C7B756);
    c = md5_FF(c, d, a, b, x[k + 2], S13, 0x242070DB);
    b = md5_FF(b, c, d, a, x[k + 3], S14, 0xC1BDCEEE);
    a = md5_FF(a, b, c, d, x[k + 4], S11, 0xF57C0FAF);
    d = md5_FF(d, a, b, c, x[k + 5], S12, 0x4787C62A);
    c = md5_FF(c, d, a, b, x[k + 6], S13, 0xA8304613);
    b = md5_FF(b, c, d, a, x[k + 7], S14, 0xFD469501);
    a = md5_FF(a, b, c, d, x[k + 8], S11, 0x698098D8);
    d = md5_FF(d, a, b, c, x[k + 9], S12, 0x8B44F7AF);
    c = md5_FF(c, d, a, b, x[k + 10], S13, 0xFFFF5BB1);
    b = md5_FF(b, c, d, a, x[k + 11], S14, 0x895CD7BE);
    a = md5_FF(a, b, c, d, x[k + 12], S11, 0x6B901122);
    d = md5_FF(d, a, b, c, x[k + 13], S12, 0xFD987193);
    c = md5_FF(c, d, a, b, x[k + 14], S13, 0xA679438E);
    b = md5_FF(b, c, d, a, x[k + 15], S14, 0x49B40821);
    a = md5_GG(a, b, c, d, x[k + 1], S21, 0xF61E2562);
    d = md5_GG(d, a, b, c, x[k + 6], S22, 0xC040B340);
    c = md5_GG(c, d, a, b, x[k + 11], S23, 0x265E5A51);
    b = md5_GG(b, c, d, a, x[k + 0], S24, 0xE9B6C7AA);
    a = md5_GG(a, b, c, d, x[k + 5], S21, 0xD62F105D);
    d = md5_GG(d, a, b, c, x[k + 10], S22, 0x2441453);
    c = md5_GG(c, d, a, b, x[k + 15], S23, 0xD8A1E681);
    b = md5_GG(b, c, d, a, x[k + 4], S24, 0xE7D3FBC8);
    a = md5_GG(a, b, c, d, x[k + 9], S21, 0x21E1CDE6);
    d = md5_GG(d, a, b, c, x[k + 14], S22, 0xC33707D6);
    c = md5_GG(c, d, a, b, x[k + 3], S23, 0xF4D50D87);
    b = md5_GG(b, c, d, a, x[k + 8], S24, 0x455A14ED);
    a = md5_GG(a, b, c, d, x[k + 13], S21, 0xA9E3E905);
    d = md5_GG(d, a, b, c, x[k + 2], S22, 0xFCEFA3F8);
    c = md5_GG(c, d, a, b, x[k + 7], S23, 0x676F02D9);
    b = md5_GG(b, c, d, a, x[k + 12], S24, 0x8D2A4C8A);
    a = md5_HH(a, b, c, d, x[k + 5], S31, 0xFFFA3942);
    d = md5_HH(d, a, b, c, x[k + 8], S32, 0x8771F681);
    c = md5_HH(c, d, a, b, x[k + 11], S33, 0x6D9D6122);
    b = md5_HH(b, c, d, a, x[k + 14], S34, 0xFDE5380C);
    a = md5_HH(a, b, c, d, x[k + 1], S31, 0xA4BEEA44);
    d = md5_HH(d, a, b, c, x[k + 4], S32, 0x4BDECFA9);
    c = md5_HH(c, d, a, b, x[k + 7], S33, 0xF6BB4B60);
    b = md5_HH(b, c, d, a, x[k + 10], S34, 0xBEBFBC70);
    a = md5_HH(a, b, c, d, x[k + 13], S31, 0x289B7EC6);
    d = md5_HH(d, a, b, c, x[k + 0], S32, 0xEAA127FA);
    c = md5_HH(c, d, a, b, x[k + 3], S33, 0xD4EF3085);
    b = md5_HH(b, c, d, a, x[k + 6], S34, 0x4881D05);
    a = md5_HH(a, b, c, d, x[k + 9], S31, 0xD9D4D039);
    d = md5_HH(d, a, b, c, x[k + 12], S32, 0xE6DB99E5);
    c = md5_HH(c, d, a, b, x[k + 15], S33, 0x1FA27CF8);
    b = md5_HH(b, c, d, a, x[k + 2], S34, 0xC4AC5665);
    a = md5_II(a, b, c, d, x[k + 0], S41, 0xF4292244);
    d = md5_II(d, a, b, c, x[k + 7], S42, 0x432AFF97);
    c = md5_II(c, d, a, b, x[k + 14], S43, 0xAB9423A7);
    b = md5_II(b, c, d, a, x[k + 5], S44, 0xFC93A039);
    a = md5_II(a, b, c, d, x[k + 12], S41, 0x655B59C3);
    d = md5_II(d, a, b, c, x[k + 3], S42, 0x8F0CCC92);
    c = md5_II(c, d, a, b, x[k + 10], S43, 0xFFEFF47D);
    b = md5_II(b, c, d, a, x[k + 1], S44, 0x85845DD1);
    a = md5_II(a, b, c, d, x[k + 8], S41, 0x6FA87E4F);
    d = md5_II(d, a, b, c, x[k + 15], S42, 0xFE2CE6E0);
    c = md5_II(c, d, a, b, x[k + 6], S43, 0xA3014314);
    b = md5_II(b, c, d, a, x[k + 13], S44, 0x4E0811A1);
    a = md5_II(a, b, c, d, x[k + 4], S41, 0xF7537E82);
    d = md5_II(d, a, b, c, x[k + 11], S42, 0xBD3AF235);
    c = md5_II(c, d, a, b, x[k + 2], S43, 0x2AD7D2BB);
    b = md5_II(b, c, d, a, x[k + 9], S44, 0xEB86D391);
    a = md5_AddUnsigned(a, AA);
    b = md5_AddUnsigned(b, BB);
    c = md5_AddUnsigned(c, CC);
    d = md5_AddUnsigned(d, DD);
  }
  return (md5_WordToHex(a) + md5_WordToHex(b) + md5_WordToHex(c) + md5_WordToHex(d)).toLowerCase();
}

  // 前端逻辑
(function() {
  var SCHOOLS = [];

  // 加载学校列表
  function loadSchools(callback) {
    var jsonPath = 'schools.json';
    var xhr = new XMLHttpRequest();
    xhr.open('GET', jsonPath, true);
    xhr.onreadystatechange = function() {
      if (xhr.readyState === 4) {
        if (xhr.status === 200) {
          try {
            var data = JSON.parse(xhr.responseText);
            SCHOOLS = data.schools || [];
          } catch(e) {
            SCHOOLS = [];
          }
        } else {
          SCHOOLS = [];
        }
        console.log('学校列表:', SCHOOLS.length, '所');
        if (callback) callback();
      }
    };
    xhr.send();
  }

  // 解析查询参数
  function getQueryParams() {
    var params = new URLSearchParams(window.location.search);
    return {
      code: params.get('code') || '',
      name: params.get('name') || ''
    };
  }

  // 首页搜索
  function renderIndex() {
    var input = document.getElementById('searchInput');
    var results = document.getElementById('results');
    if (!input || !results) return;

    function doSearch(v) {
      var q = (v || '').trim().toLowerCase();
      results.innerHTML = '';
      
      if (!q) {
        results.style.display = 'none';
        return;
      }
      
      var matched = SCHOOLS.filter(function(s) {
        return s.code.toLowerCase().indexOf(q) !== -1 || 
               (s.name && s.name.toLowerCase().indexOf(q) !== -1);
      });
      
      if (matched.length === 0) {
        results.style.display = 'none';
        return;
      }
      
      matched.forEach(function(s) {
        var li = document.createElement('li');
        li.className = 'item';
        li.innerHTML = '<span class="code">' + s.code + '</span><span class="name">' + (s.name || '') + '</span>';
        li.onclick = function() {
          window.location.href = 'subscribe.html?code=' + encodeURIComponent(s.code) + '&name=' + encodeURIComponent(s.name || '');
        };
        results.appendChild(li);
      });
      results.style.display = 'block';
    }

    input.oninput = function(e) {
      doSearch(e.target.value);
    };
  }

  // 订阅页
  function renderSubscribe() {
    var params = getQueryParams();
    var code = params.code;
    var name = params.name;

    if (!code) {
      window.location.href = 'index.html';
      return;
    }

    var nameEl = document.getElementById('schoolName');
    if (nameEl) {
      nameEl.textContent = name ? '学校：' + name + ' (' + code + ')' : '学校代码：' + code;
    }

    var codeEl = document.getElementById('school_code');
    if (codeEl) codeEl.value = code;

    var genBtn = document.getElementById('generate');
    var loadingEl = document.getElementById('loading');
    if (genBtn) {
      genBtn.onclick = function() {
        var username = document.getElementById('username').value.trim();
        var password = document.getElementById('password').value.trim();
        var remindTime = (document.getElementById('remindTime').value.trim() || '30');

        if (!username || !password) {
          showError('请填写用户名和密码');
          return;
        }

        // 显示加载动画，禁用按钮
        if (loadingEl) loadingEl.style.display = 'flex';
        genBtn.disabled = true;
        hideError();
        var resultEl = document.getElementById('result');
        if (resultEl) resultEl.style.display = 'none';

        // 将密码转换为 MD5
        var md5Password = md5(password);

        var verifyUrl = API_BASE_URL + '/' + encodeURIComponent(username) + '.ics?pwd=' + md5Password + '&remindTime=' + encodeURIComponent(remindTime) + '&school_code=' + encodeURIComponent(code) + '&all_semesters=true&force=true';

        var icsUrl = API_BASE_URL + '/' + encodeURIComponent(username) + '.ics?pwd=' + md5Password + '&remindTime=' + encodeURIComponent(remindTime) + '&school_code=' + encodeURIComponent(code) + '&all_semesters=true';

        var xhr = new XMLHttpRequest();
        xhr.open('GET', verifyUrl, true);
        xhr.onreadystatechange = function() {
          // 恢复按钮状态
          if (loadingEl) loadingEl.style.display = 'none';
          genBtn.disabled = false;
          
          if (xhr.readyState === 4) {
            if (xhr.status === 200) {
              var urlInput = document.getElementById('subscribeUrl');
              if (urlInput) urlInput.value = icsUrl;
              if (resultEl) resultEl.style.display = 'block';
              hideError();
            } else {
              // 尝试解析 API 返回的错误信息
              var errorMsg = '生成订阅失败';
              try {
                var errData = JSON.parse(xhr.responseText);
                if (errData.detail) {
                  errorMsg = errData.detail;
                }
              } catch(e) {
                // 如果解析失败，使用默认消息
              }
              showError(errorMsg);
            }
          }
        };
        xhr.send();
      };
    }

    var copyBtn = document.getElementById('copy');
    if (copyBtn) {
      copyBtn.onclick = function() {
        var urlInput = document.getElementById('subscribeUrl');
        if (urlInput) {
          urlInput.select();
          document.execCommand('copy');
          copyBtn.textContent = '已复制';
          setTimeout(function() { copyBtn.textContent = '复制'; }, 2000);
        }
      };
    }
  }

  function showError(msg) {
    var err = document.getElementById('error');
    if (err) {
      err.textContent = msg;
      err.style.display = 'block';
    }
  }

  function hideError() {
    var err = document.getElementById('error');
    if (err) err.style.display = 'none';
  }

  // 入口
  document.addEventListener('DOMContentLoaded', function() {
    var path = window.location.pathname;
    var isSubscribePage = path.indexOf('/subscribe.html') !== -1 || path.indexOf('subscribe.html') !== -1;
    
    loadSchools(function() {
      if (isSubscribePage) {
        renderSubscribe();
      } else {
        renderIndex();
      }
    });
  });
})();
