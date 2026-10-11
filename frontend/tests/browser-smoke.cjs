/* Run against this owned local application. No existing browser profile is used. */
const {chromium}=require('@playwright/test');
const fs=require('fs');const path=require('path');
(async()=>{
 const output=path.resolve('../playwright-artifacts/'+new Date().toISOString().replace(/[:.]/g,'-'));fs.mkdirSync(output,{recursive:true});
 const options={headless:true};if(process.platform==='win32')options.executablePath='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
 const browser=await chromium.launch(options);const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));await page.goto(process.env.APP_URL||'http://127.0.0.1:8000');await page.getByRole('heading',{name:'Overview',exact:true}).waitFor();
 await page.getByRole('button',{name:'Create promotion plan',exact:true}).click();await page.getByRole('button',{name:'Generate promotion plan',exact:true}).click();
 await page.getByText('The plan is ready',{exact:true}).waitFor({timeout:120000});
 await page.getByRole('button',{name:'Generate promotion plan',exact:true}).waitFor();await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Generate promotion plan'));return b&&!b.disabled;},{},{timeout:45000});
 await page.screenshot({path:path.join(output,'planner-desktop.png'),fullPage:true});
 await page.getByRole('button',{name:'Simulation',exact:true}).click();await page.getByText('Contribution under uncertainty',{exact:true}).waitFor();await page.screenshot({path:path.join(output,'simulation-desktop.png'),fullPage:true});
 await page.getByRole('button',{name:'Decision record',exact:true}).click();await page.getByRole('heading',{name:'Decision record',exact:true}).waitFor();
 await page.getByRole('button',{name:'Approval & activity',exact:true}).click();
 console.log('APPROVAL_BUTTONS',await page.getByRole('button').allTextContents());
 await page.getByRole('button',{name:'Approve revision',exact:true}).click();await page.getByRole('button',{name:'Activate in sandbox',exact:true}).waitFor();await page.getByRole('button',{name:'Activate in sandbox',exact:true}).click();
 await page.getByRole('button',{name:'Pause plan',exact:true}).waitFor({timeout:20000});
 await page.screenshot({path:path.join(output,'approval-desktop.png'),fullPage:true});
 const planResponse=await page.request.get((process.env.APP_URL||'http://127.0.0.1:8000')+'/api/v1/plans');const active=(await planResponse.json()).find(p=>p.status==='active');
 const offer=active.offers.slice(0,10).find(c=>c.start_day===0);if(!offer)throw Error('Fixture has no currently redeemable offer');
 await page.getByRole('button',{name:'Retail sandbox',exact:true}).click();
 await page.locator('tr').filter({hasText:offer.name}).filter({hasText:offer.city}).first().getByRole('button',{name:'Redeem once',exact:true}).click();
 await page.getByText('fulfilled',{exact:true}).waitFor({timeout:15000});
 await page.getByRole('button',{name:'Approval & activity',exact:true}).click();await page.getByRole('button',{name:'Apply event and replan',exact:true}).click();
 await page.getByText('The plan is ready',{exact:true}).waitFor({timeout:120000});await page.getByRole('button',{name:'Generate promotion plan',exact:true}).waitFor();await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Generate promotion plan'));return b&&!b.disabled;},{},{timeout:45000});
 const revisions=await (await page.request.get((process.env.APP_URL||'http://127.0.0.1:8000')+'/api/v1/plans')).json();if(!revisions.some(p=>p.parent_id&&p.revision===2))throw Error('Event did not produce a new revision');
 for(const view of ['Evidence inbox','Integrations','Evaluation']){await page.getByRole('button',{name:view,exact:true}).click();await page.getByRole('heading',{name:view,exact:true}).waitFor();}
 await page.getByRole('button',{name:'Overview',exact:true}).click();await page.screenshot({path:path.join(output,'overview-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);await page.screenshot({path:path.join(output,'overview-mobile.png'),fullPage:true});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
 const report={page_errors:errors,mobile_overflow:overflow,screenshots:output,completed:true};fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 await browser.close();if(errors.length||overflow)process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
