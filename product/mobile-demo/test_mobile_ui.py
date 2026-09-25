import asyncio,json,os,pathlib
from playwright.async_api import async_playwright

async def main():
 p=pathlib.Path(__file__).resolve().with_name('index.html')
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--disable-gpu'])
  context=await browser.new_context(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,accept_downloads=True)
  page=await context.new_page()
  page_errors=[]
  page.on('pageerror', lambda error: page_errors.append(str(error)))
  await page.set_content(p.read_text(),wait_until='load',timeout=15000)
  await page.get_by_role('button',name='Ver proyecto demo').click()
  assert await page.locator('#view-proyectos').is_visible()
  assert not await page.get_by_text('0 reales').is_visible()
  async with page.expect_download() as info:
   await page.get_by_role('button',name='Exportar fixture JSON').click()
  d=await info.value; path=await d.path(); fixture=json.loads(pathlib.Path(path).read_text())
  assert fixture['test_only'] is True and fixture['engine_connected'] is False
  assert fixture['event_log_is_authentic'] is False and fixture['scientific_authority']=='NONE'
  await page.get_by_role('button',name='Historial',exact=True).click()
  assert await page.locator('#view-historial').is_visible()
  await page.get_by_role('button',name='Seguridad',exact=True).click()
  assert await page.locator('#view-evidencias').is_visible()
  await page.get_by_role('button',name='Inicio',exact=True).click()
  assert await page.locator('#view-inicio').is_visible()
  await page.wait_for_timeout(350)
  await page.screenshot(path=os.environ.get('QROS_MOBILE_SCREENSHOT','/tmp/qros_mobile_m0_preview.png'),full_page=False)
  assert not page_errors,page_errors
  print('MOBILE_BROWSER_TEST_PASS: mobile_390x844 tab_navigation_and_download_fixture')
  print('MOBILE_TEST_FIXTURE',json.dumps(fixture,sort_keys=True))
  await browser.close()

asyncio.run(main())
