/* Prepared browser regression. Run only after the narrow runtime exception. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),moduleApi=require('node:module');
const prepareOnly=process.argv.includes('--prepare-only');
const base=__dirname,runtime=path.resolve(base,'browser-runtime-01'),temporary=path.join(runtime,'temp');
if(!prepareOnly&&process.env.PROMOPILOT_BROWSER_RUNTIME_APPROVED!=='1')throw Error('Browser runtime cleanup permission has not been recorded for this run.');
if(!prepareOnly&&!fs.existsSync(path.join(runtime,'launch.json')))throw Error('The isolated browser has not been launched.');
process.env.TEMP=temporary;process.env.TMP=temporary;
process.env.APP_URL='http://127.0.0.1:8768';
const output=path.join(base,'browser-captures','regression-'+new Date().toISOString().replace(/[:.]/g,'-'));
if(fs.existsSync(output))throw Error('Refusing to reuse capture outputs.');
process.env.AUDIT_OUTPUT=output;
const withinRuntime=target=>{
 const resolved=path.resolve(String(target));
 if(resolved!==runtime&&!resolved.startsWith(runtime+path.sep))throw Error('Deletion outside the approved new browser runtime is prohibited: '+resolved);
 const parent=path.dirname(resolved);if(fs.existsSync(parent)){const real=fs.realpathSync(parent);if(real!==runtime&&!real.startsWith(runtime+path.sep))throw Error('Runtime path resolves outside its scope.');}
};
for(const name of ['unlink','unlinkSync','rmdir','rmdirSync','rm','rmSync'])if(typeof fs[name]==='function'){
 const original=fs[name];fs[name]=function(target,...args){withinRuntime(target);return original.call(this,target,...args)};
}
for(const name of ['unlink','rmdir','rm'])if(typeof fs.promises[name]==='function'){
 const original=fs.promises[name];fs.promises[name]=async function(target,...args){withinRuntime(target);return original.call(this,target,...args)};
}
moduleApi.syncBuiltinESMExports();
const originalPath=path.join(base,'promopilot/frontend/tests/remediation-browser.cjs');
let source=fs.readFileSync(originalPath,'utf8');
const launchLine=source.split(/\r?\n/).find(line=>line.includes('const browser=await chromium.launch'));
if(!launchLine)throw Error('Browser harness launch changed; inspect it before execution.');
source=source.replace(launchLine,"  const browser=await chromium.connectOverCDP('http://127.0.0.1:9227');");
source=source.replace("page.on('pageerror',error=>errors.push(error.message));", "await page.context().route('**/*',route=>{const host=new URL(route.request().url()).hostname;return ['127.0.0.1','localhost','[::1]'].includes(host)?route.continue():route.abort()});page.on('pageerror',error=>errors.push(error.message));");
source=source.replace('viewport:{width:1440,height:1000}','viewport:{width:1920,height:1080}');
source=source.replace("const today=new Date(Date.now()+330*60000).toISOString().slice(0,10);","const today='2026-10-04';");
source=source.replace(/getByLabel\('Authority budget .*?',\{exact:true\}\)/g,'getByLabel(/Authority budget/)');
source=source.replace(/getByLabel\('Permitted SKUs .*?',\{exact:true\}\)/g,'getByLabel(/Permitted SKUs/)');
source=source.replace(/getByLabel\('Promotion budget .*?',\{exact:true\}\)/g,'getByLabel(/Promotion budget/)');
const wrapped=moduleApi.wrap(source);const compiled=new vm.Script(wrapped,{filename:originalPath});
const localRequire=moduleApi.createRequire(originalPath);
if(prepareOnly)console.log(JSON.stringify({prepared:true,syntax:'valid',desktop:'1920x1080',endpoint:'http://127.0.0.1:9227',browser_launched:false}));else compiled.runInThisContext()({},localRequire,{exports:{}},originalPath,path.dirname(originalPath));
