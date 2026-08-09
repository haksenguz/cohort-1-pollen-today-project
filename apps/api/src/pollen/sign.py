"""The `/` page — for humans who opened the API host in a browser."""

SIGN_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>server: alive!</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    background: #0e1013; color: #f2f4f6; overflow: hidden;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
  }
  .sign { text-align: center; padding: 24px; }
  .status {
    font-size: clamp(28px, 7vw, 56px); font-weight: 700; letter-spacing: -0.02em;
    display: inline-flex; align-items: center; gap: 14px;
  }
  .pulse {
    width: 16px; height: 16px; border-radius: 50%; background: #10b981;
    box-shadow: 0 0 0 0 rgba(16,185,129,.7); animation: pulse 1.8s infinite;
  }
  @keyframes pulse {
    0%   { box-shadow: 0 0 0 0 rgba(16,185,129,.7); }
    70%  { box-shadow: 0 0 0 18px rgba(16,185,129,0); }
    100% { box-shadow: 0 0 0 0 rgba(16,185,129,0); }
  }
  .cooking { margin-top: 18px; font-size: clamp(15px, 3.5vw, 20px); color: #9aa3ad; }
  .pan { display: inline-block; animation: shake 1.1s ease-in-out infinite; }
  @keyframes shake {
    0%,100% { transform: translateX(0) rotate(0); }
    25%     { transform: translateX(-5px) rotate(-9deg); }
    75%     { transform: translateX(5px) rotate(9deg); }
  }
  .dots::after { content: ""; animation: dots 1.6s steps(4, end) infinite; }
  @keyframes dots {
    0% { content: ""; } 25% { content: "."; }
    50% { content: ".."; } 75% { content: "..."; }
  }
  .links { margin-top: 34px; font-size: 14px; color: #6b7280; }
  .links a { color: #9aa3ad; text-decoration: none; border-bottom: 1px solid #262b32; }
  .links a:hover { color: #f2f4f6; }
  @media (prefers-reduced-motion: reduce) {
    .pulse, .pan, .dots::after { animation: none; }
    .dots::after { content: "..."; }
  }
</style></head>
<body>
  <div class="sign">
    <div class="status"><span class="pulse"></span> server: alive!</div>
    <div class="cooking"><span class="pan">\U0001f373</span> Ismail is cooking<span class="dots"></span></div>
    <div class="links">
      <a href="/graphql">/graphql</a> &nbsp;·&nbsp; <a href="/api/health">/api/health</a>
    </div>
  </div>
</body></html>"""
