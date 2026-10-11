/* Real local API/UI regression. Uses a fresh browser context and offline data. */
const {chromium,expect}=require('@playwright/test');
const fs=require('fs'),path=require('path');
const base=process.env.APP_URL||'http://127.0.0.1:8000';
if(!['127.0.0.1','localhost','[::1]'].includes(new URL(base).hostname))throw Error('This fixture workflow only runs against a local server.');
const output=process.env.AUDIT_OUTPUT||path.resolve(__dirname,'../../playwright-artifacts/remediation-'+new Date().toISOString().replace(/[:.]/g,'-'));
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,...(process.platform==='win32'?{executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(base);await page.getByRole('heading',{name:'Overview',exact:true}).waitFor();
    const session=await(await page.request.get(base+'/api/v1/session')).json();
    const post=async(route,data)=>{const response=await page.request.post(base+'/api/v1'+route,{data,headers:{'x-csrf-token':session.csrf}});if(!response.ok())throw Error(route+' '+response.status()+' '+await response.text());return response.json()};
    const today=new Date(Date.now()+330*60000).toISOString().slice(0,10);
    const narrow={max_budget_paise:100000,max_discount_bps:500,min_margin_bps:2000,cities:['Delhi'],mechanisms:['coupon'],allow_auto_replan:false,permitted_skus:['SKU001'],date_from:today,date_to:today,max_changed_offer_fraction:0.1};
    await post('/envelope',narrow);
    const plans=[];
    for(let index=0;index<4;index++){
      let run=await post('/plans',{title:'History regression '+index,mode:'offline',scenarios:20});
      for(let step=0;step<16&&!['validated','failed','needs_input','completed'].includes(run.state);step++)run=await post('/runs/'+run.id+'/advance',{});
      if(run.state!=='validated')throw Error('Offline fixture did not validate: '+JSON.stringify(run));
      const plan=await(await page.request.get(base+'/api/v1/plans/'+run.plan_id)).json();plans.push(plan);
      if(index===0){await post('/plans/'+plan.id+'/approve',{revision:plan.revision});await post('/plans/'+plan.id+'/execute',{revision:plan.revision})}
    }
    await page.reload();await page.getByRole('heading',{name:'Overview',exact:true}).waitFor();
    const selector=page.getByRole('combobox',{name:'Select saved plan',exact:true});
    await expect(selector.locator('option')).toHaveCount(4);await expect(selector).toHaveValue(plans[0].id);
    await selector.selectOption(plans[3].id);await selector.selectOption(plans[0].id);
    await page.getByRole('button',{name:'Approval & activity',exact:true}).click();
    await expect(page.getByRole('button',{name:'Pause plan',exact:true})).toBeVisible();
    await expect(page.getByLabel('Authority budget · INR',{exact:true})).toHaveValue('1000');
    await expect(page.getByLabel('Permitted SKUs · comma separated',{exact:true})).toHaveValue('SKU001');
    await page.getByLabel('Allow automatic sandbox activation after an event',{exact:true}).check();
    await page.getByLabel('I reviewed the displayed limits and authorize this expanded sandbox authority.',{exact:true}).check();
    const saved=page.waitForResponse(response=>response.url().endsWith('/envelope')&&response.request().method()==='POST');
    await page.getByRole('button',{name:'Save authority envelope',exact:true}).click();
    const actual=await(await saved).json();expect(actual).toEqual({...narrow,allow_auto_replan:true});
    await expect(page.getByRole('button',{name:'Save authority envelope',exact:true})).toBeEnabled();
    await page.screenshot({path:path.join(output,'authority-preserved.png'),fullPage:true});
    await page.getByRole('button',{name:'Plan workspace',exact:true}).click();
    await page.getByLabel('Promotion budget · INR',{exact:true}).fill('-1');
    await page.getByRole('button',{name:'Generate promotion plan',exact:true}).click();
    await expect(page.getByRole('alert')).toContainText('budget paise');
    await expect(page.getByRole('alert')).toContainText('greater than or equal to 0');
    await page.setViewportSize({width:390,height:844});
    await page.getByLabel('Open navigation',{exact:true}).click();await page.getByRole('button',{name:'Approval & activity',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
    await page.screenshot({path:path.join(output,'authority-mobile.png'),fullPage:true});
    expect(errors).toEqual([]);expect(overflow).toBe(false);
    const report={completed:true,page_errors:errors,mobile_overflow:overflow,checks:['four saved plans selectable','oldest active plan selected after reload','pause action reachable','all authority limits preserved when enabling automation','field-specific validation message','authority mobile layout']};
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
