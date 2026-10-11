/* Extended audit against this owned app, using an isolated temporary browser context. */
const {chromium,expect}=require('@playwright/test');
const fs=require('fs'),path=require('path');
(async()=>{
 const base=process.env.APP_URL||'http://127.0.0.1:8000';
 const output=path.resolve('../playwright-artifacts/audit-'+new Date().toISOString().replace(/[:.]/g,'-'));fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,...(process.platform==='win32'?{executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[],overflow=[];
 page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.getByRole('heading',{name:'Overview',exact:true}).waitFor();
 const session=await(await page.request.get(base+'/api/v1/session')).json();
 const send=async(route,data={})=>{const r=await page.request.post(base+'/api/v1'+route,{data,headers:{'x-csrf-token':session.csrf}});if(!r.ok())throw Error(route+' '+r.status()+' '+await r.text());return r.json()};
 const first=await send('/plans',{title:'Audit recovery plan',mode:'offline',scenarios:20});
 await page.reload();await page.getByRole('button',{name:'Plan workspace',exact:true}).click();
 await page.getByRole('button',{name:'Resume saved run',exact:true}).click();await page.getByText('The plan is ready',{exact:true}).waitFor({timeout:120000});
 await expect(page.getByRole('button',{name:'Generate promotion plan',exact:true})).toBeEnabled({timeout:30000});
 await page.getByRole('button',{name:'Simulation',exact:true}).click();await page.getByLabel('Scenario count').selectOption('100');
 const simulationResponse=page.waitForResponse(r=>r.url().endsWith('/simulate')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Run simulation',exact:true}).click();const override=await(await simulationResponse).json();
 await expect(page.getByRole('button',{name:'Run simulation',exact:true})).toBeEnabled({timeout:30000});
 let second=await send('/plans',{title:'Audit second plan',cities:['Delhi'],objective:'clearance',mode:'offline',scenarios:20});
 for(let i=0;i<7;i++)second=await send('/runs/'+second.id+'/advance');if(second.state!=='validated')throw Error('Second plan: '+JSON.stringify(second));
 const planB=await(await page.request.get(base+'/api/v1/plans/'+second.plan_id)).json();
 // Trigger the normal application refresh without reloading (the old simulation state must remain scoped).
 await page.locator('nav').getByRole('button',{name:/^Evidence inbox/}).click();
 await page.locator('.fixture-list > div').filter({hasText:'grocery-policy.pdf'}).getByRole('button').click();
 await page.getByRole('button',{name:'Review fields',exact:true}).first().waitFor();
 await page.getByRole('button',{name:'Overview',exact:true}).click();await page.locator('.plan-row').filter({hasText:'Audit second plan'}).click();
 await page.getByRole('button',{name:'Simulation',exact:true}).click();
 const money=v=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',minimumFractionDigits:0,maximumFractionDigits:2}).format(v/100);
 await expect(page.locator('.metric').filter({hasText:'Expected incremental contribution'}).locator('strong')).toHaveText(money(planB.simulation.incremental_contribution_paise));
 await page.locator('nav').getByRole('button',{name:/^Evidence inbox/}).click();await page.getByRole('button',{name:'Review fields',exact:true}).first().click();
 let dialog=page.getByRole('dialog');await page.keyboard.press('Shift+Tab');if(!await page.evaluate(()=>document.querySelector('[role=dialog]').contains(document.activeElement)))throw Error('Modal focus escaped');await page.keyboard.press('Escape');await expect(dialog).toHaveCount(0);await page.getByRole('button',{name:'Review fields',exact:true}).first().click();dialog=page.getByRole('dialog');await expect(dialog.getByLabel('currency',{exact:true})).toHaveValue('INR');
 await dialog.getByLabel('budget paise (INR paise)',{exact:true}).fill('3.5');await dialog.getByRole('button',{name:'Confirm and apply new version'}).click();
 await expect(dialog.getByRole('alert')).toBeVisible();await expect(dialog).toBeVisible();
 await dialog.getByLabel('budget paise (INR paise)',{exact:true}).fill('3000000');await dialog.getByRole('button',{name:'Confirm and apply new version'}).click();await expect(dialog).toHaveCount(0);
 await page.screenshot({path:path.join(output,'evidence-confirmed.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 for(const name of ['Overview','Evidence inbox','Plan workspace','Simulation','Decision record','Approval & activity','Retail sandbox','Integrations','Evaluation']){
   await page.getByLabel('Open navigation',{exact:true}).click();await page.locator('nav').getByRole('button',{name,exact:false}).click();
   await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))overflow.push(name);
 }
 await page.screenshot({path:path.join(output,'evaluation-mobile.png'),fullPage:true});
 const docs=await page.request.get(base+'/docs');if(!docs.headers()['content-security-policy'].includes('https://cdn.jsdelivr.net'))throw Error('API documentation assets are blocked by CSP');
 const report={completed:true,page_errors:errors,mobile_overflow_views:overflow,scenarios:['resume after reload','plan-specific simulation results','human confirmation','keyboard focus and Escape','invalid correction kept visible','nine mobile views','API documentation CSP'],first_plan:first.plan_id,second_plan:second.plan_id,prior_simulation_plan:override.plan_id,screenshots:output};
 fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));await browser.close();
 if(errors.length||overflow.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
