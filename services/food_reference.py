"""Small editorial reference catalog, distinct from measured nutrient composition.
Numbers describe source servings/recipes, never the user's actual serving.
No bulk ThaiFCD copy or automatic nutrition/health score.
"""
ANAMAI='https://multimedia.anamai.moph.go.th/news/120865-2/'
EGG='https://multimedia.anamai.moph.go.th/news/news141065/'
RICE='https://nutrition2.anamai.moph.go.th/web-upload/6x22caac0452648c8dd1f534819ba2f16c/202012/m_news/9419/194519/file_download/a7030e407e74664054ab01f09ced363c.pdf'
PLATE='https://www.niddk.nih.gov/health-information/diabetes/overview/healthy-living-with-diabetes'
FOODS=[
 {'id':'chicken_rice','name':'ข้าวมันไก่','aliases':['ข้าวมันไก่ต้ม'],'kcal':[558,619],'basis':'1 จานตามตัวอย่างในแหล่งอ้างอิง','url':ANAMAI,'published':'2022-08-12','note':'สูตร ข้าว หนังไก่ และน้ำจิ้มทำให้พลังงานต่างกัน'},
 {'id':'plain_chicken_rice','name':'ข้าวสวยกับไก่ต้ม','aliases':['ข้าวไก่ต้ม'],'kcal':[505,539],'basis':'ข้าวมันไก่ที่เปลี่ยนเป็นข้าวสวย 1 จานตามแหล่งอ้างอิง','url':ANAMAI,'published':'2022-08-12','note':'ไม่ใช่ค่าพลังงานของข้าวสวยหรือเนื้อไก่แยกส่วน'},
 {'id':'palo','name':'ต้มพะโล้','aliases':['พะโล้'],'kcal':[358,358],'basis':'1 ถ้วยตามแหล่งอ้างอิง ไม่รวมข้าว','url':ANAMAI,'published':'2022-08-12','note':'แหล่งเดียวกันรายงานโซเดียมประมาณ 556 มก. ต่อถ้วย สูตรจริงอาจต่างกัน'},
 {'id':'egg_rice','name':'ข้าวผัดไข่','aliases':[],'kcal':[509.25,509.25],'basis':'สูตรสำหรับ 1 คนในเอกสาร ไม่ใช่ทุกจานตามร้าน','url':RICE,'published':None,'note':'น้ำมันและข้าวในสูตรจริงอาจต่างจากสูตรอ้างอิง'},
 {'id':'egg_bean','name':'ยำไข่ต้มใส่ถั่วแดง','aliases':[],'kcal':[113,113],'basis':'เมนูตามสูตรตัวอย่าง ไม่รวมข้าว','url':EGG,'published':'2022-10-14','note':'ยังไม่ทราบน้ำหนักเสิร์ฟในข่าว จึงใช้เปรียบเทียบสูตรทั่วไปไม่ได้'},
 {'id':'pumpkin_egg','name':'ฟักทองผัดไข่','aliases':[],'kcal':[118,118],'basis':'เมนูตามสูตรตัวอย่าง ไม่รวมข้าว','url':EGG,'published':'2022-10-14','note':'ยังไม่ทราบน้ำหนักเสิร์ฟในข่าว จึงใช้เปรียบเทียบสูตรทั่วไปไม่ได้'},
 {'id':'bubble_tea','name':'ชานมไข่มุก','aliases':[],'kcal':[240,360],'basis':'1 แก้วตามแหล่งอ้างอิง ขนาดแก้วไม่ได้ระบุ','url':'https://multimedia.anamai.moph.go.th/infographics/bubble-milk-tea/','published':'2019-09-06','note':'ความหวาน ขนาดแก้ว และไข่มุกเปลี่ยนพลังงานได้มาก'},
]

# Small, manually checked factual serving references; no images or full tables.
# Source pages describe example dishes, not a measured restaurant portion.
SIRIRAJ_DISHES='https://www.si.mahidol.ac.th/th/division/hph/admin/news_files/689_49_1.pdf'
SIRIRAJ_EXCHANGE='https://www.si.mahidol.ac.th/sirirajdoctor/article_detail.aspx?ID=1477'
TOM_YUM='https://region8.prd.go.th/th/content/category/detail/id/495/iid/346138'
CMU_MILK='https://sriphat.med.cmu.ac.th/th/knowledge-68'
for ident,name,kcal,aliases,page in [
 ('pork_leg_rice','ข้าวขาหมู',690,[],5),
 ('omelette_rice','ข้าวไข่เจียว',440,[],5),
 ('fried_chicken_rice','ข้าวมันไก่ทอด',557,[],5),
 ('fried_rice','ข้าวผัด',561,[],5),
 ('pad_see_ew','ผัดซีอิ๊ว',658,['ผัดซีอิ้ว','ผัดซีอิว'],5),
 ('chicken_noodles','ก๋วยเตี๋ยวคั่วไก่',603,[],4),
 ('macaroni','ผัดมักกะโรนี',536,[],4),
 ('pad_thai','ผัดไทย',557,['ผัดไท'],4),
 ('chicken_biryani','ข้าวหมกไก่',481,[],4),
 ('basil_chicken_egg','ข้าวกะเพราไก่ไข่ดาว',545,['ข้าวราดผัดกระเพราไก่ไข่ดาว','ข้าวกระเพราไก่ไข่ดาว','ข้าวผัดกะเพราไก่ไข่ดาว'],4),
 ('carbonara','สปาเกตตี้คาโบนาร่า',470,['สปาเก็ตตี้คาโบนาร่า'],4),
]:
    FOODS.append({'id':ident,'name':name,'aliases':aliases,'kcal':[kcal,kcal],
                  'basis':'1 จานตัวอย่างในเอกสาร (ไม่ระบุน้ำหนักเสิร์ฟ)',
                  'url':SIRIRAJ_DISHES,'published':None,'publisher':'ศิริราชพยาบาล มหาวิทยาลัยมหิดล',
                  'location':f'PDF หน้า {page} หัวข้ออาหารจานเดียว',
                  'note':'ใช้เทียบจานทั่วไปคร่าว ๆ สูตรและขนาดจานจริงทำให้พลังงานต่างกัน'})

FOODS += [
 {'id':'plain_rice','name':'ข้าวสวย','aliases':['ข้าว'],'kcal':[80,80],'basis':'1 ทัพพีเล็ก (1/3 ถ้วย)','url':SIRIRAJ_EXCHANGE,'published':None,'publisher':'ศิริราชพยาบาล มหาวิทยาลัยมหิดล','location':'อาหารแลกเปลี่ยน หมวดข้าว แป้ง ขนมปัง','note':'ใช้ทัพพีเล็กตามแหล่งอ้างอิง ไม่แปลงจานหรือชามเป็นทัพพีเอง'},
 {'id':'boiled_egg','name':'ไข่ต้ม','aliases':['ไข่ไก่ต้ม'],'kcal':[80,80],'basis':'ไข่ไก่ 1 ฟอง ไม่เติมน้ำมัน','url':'https://anamai.moph.go.th/th/news-anamai/37872','published':'2014-10-10','location':'พลังงานของไข่ไก่ 1 ฟอง','note':'ใช้ค่าพลังงานไข่ไก่อ้างอิง ไม่รวมซอสหรือเครื่องเคียง'},
 {'id':'whole_milk','name':'นมจืดไขมันเต็ม','aliases':['นมเต็มมันเนย','นมเต็มไขมัน'],'kcal':[150,150],'basis':'240 มิลลิลิตร','url':SIRIRAJ_EXCHANGE,'published':None,'publisher':'ศิริราชพยาบาล มหาวิทยาลัยมหิดล','location':'อาหารแลกเปลี่ยน หมวดนม','note':'นมรสจืดไขมันเต็มเท่านั้น ฉลากผลิตภัณฑ์จริงอาจต่างกัน'},
 {'id':'skim_milk','name':'นมขาดมันเนย','aliases':['นมขาดไขมัน'],'kcal':[90,90],'basis':'240 มิลลิลิตร','url':CMU_MILK,'published':None,'publisher':'ศูนย์ศรีพัฒน์ คณะแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่','location':'กลุ่มน้ำนม ชนิดขาดมันเนย 240 มิลลิลิตร','note':'นมขาดไขมันรสจืด ไม่ใช้แทนนมพร่องมันเนยหรือรสหวาน'},
 {'id':'lowfat_milk','name':'นมจืดพร่องมันเนย','aliases':['นมพร่องมันเนย','นมจืดไขมันต่ำ'],'kcal':[120,120],'basis':'240 มิลลิลิตร','url':CMU_MILK,'published':None,'publisher':'ศูนย์ศรีพัฒน์ คณะแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่','location':'กลุ่มน้ำนม ชนิดพร่องมันเนย 240 มิลลิลิตร','note':'นมพร่องมันเนยรสจืด ฉลากผลิตภัณฑ์จริงอาจต่างกัน'},
 {'id':'unsweet_soy','name':'นมถั่วเหลืองไม่เติมน้ำตาล','aliases':['นมถั่วเหลืองไม่ใส่น้ำตาล'],'kcal':[75,75],'basis':'240 มิลลิลิตร','url':CMU_MILK,'published':None,'publisher':'ศูนย์ศรีพัฒน์ คณะแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่','location':'กลุ่มน้ำนมถั่วเหลือง 1 ส่วน 240 มิลลิลิตร ไม่เติมน้ำตาล','note':'ใช้เฉพาะสูตรไม่เติมน้ำตาล ไม่แทนสูตรหวานหรือสูตรใส่เครื่อง'},
 {'id':'tom_yum','name':'ต้มยำกุ้ง','aliases':[],'kcal':[270,370],'basis':'1 ถ้วยขนาดถ้วยข้าวต้มกุ๊ย ไม่รวมข้าว','url':TOM_YUM,'published':'2024-12-06','publisher':'กรมอนามัย ผ่านสำนักงานประชาสัมพันธ์ที่ 8','location':'ข่าว 6 ธันวาคม 2567 ย่อหน้าโภชนาการ','note':'ช่วงอ้างอิงน้ำใสถึงน้ำข้นเติมกะทิ ไม่ใช่ช่วงความเชื่อมั่นทางสถิติ'},
 {'id':'clear_tom_yum','name':'ต้มยำกุ้งน้ำใส','aliases':[],'kcal':[270,270],'basis':'1 ถ้วยขนาดถ้วยข้าวต้มกุ๊ย ไม่รวมข้าว','url':TOM_YUM,'published':'2024-12-06','publisher':'กรมอนามัย ผ่านสำนักงานประชาสัมพันธ์ที่ 8','location':'ข่าว 6 ธันวาคม 2567 ย่อหน้าโภชนาการ','note':'สูตรและขนาดถ้วยจริงอาจต่างกัน ไม่รวมข้าว'},
 {'id':'coconut_tom_yum','name':'ต้มยำกุ้งน้ำข้นใส่กะทิ','aliases':[],'kcal':[370,370],'basis':'1 ถ้วยขนาดถ้วยข้าวต้มกุ๊ย ไม่รวมข้าว','url':TOM_YUM,'published':'2024-12-06','publisher':'กรมอนามัย ผ่านสำนักงานประชาสัมพันธ์ที่ 8','location':'ข่าว 6 ธันวาคม 2567: 270 + กะทิเพิ่ม 100','note':'คำนวณ 270 + 100 ตามแหล่งอ้างอิง ไม่ใช้แทนสูตรน้ำข้นใส่นม'},
]
for ident,name,quantity,unit in [('guava','ฝรั่ง',1,'ผลเล็ก'),('rose_apple','ชมพู่',2,'ผล'),('rambutan','เงาะ',4,'ผล'),('papaya','มะละกอ',6,'ชิ้นคำ'),('pineapple','สับปะรด',6,'ชิ้นคำ')]:
    FOODS.append({'id':ident,'name':name,'aliases':[],'kcal':[60,60],
                  'basis':f'{quantity} {unit} ตามอาหารแลกเปลี่ยน ไม่รวมเครื่องจิ้ม',
                  'url':SIRIRAJ_EXCHANGE,'published':None,'publisher':'ศิริราชพยาบาล มหาวิทยาลัยมหิดล',
                  'location':'อาหารแลกเปลี่ยน หมวดผลไม้',
                  'serving':{'quantity':quantity,'unit':unit,'unit_factors':{'ผล':1,'ลูก':1} if unit=='ผลเล็ก' else {'ลูก':1} if unit=='ผล' else {}},
                  'note':'ขนาดผลหรือชิ้นจริงอาจต่างจากตัวอย่าง ไม่รวมพริกเกลือ น้ำตาล หรือเครื่องจิ้ม'})

# Only conversions explicitly supported by the serving source. No guessed grams
# per plate, bowl, cup or piece; absent serving metadata cannot enter a total.
SERVINGS={
 'chicken_rice':(1,'จาน',{}),'plain_chicken_rice':(1,'จาน',{}),
 'palo':(1,'ถ้วย',{}),'egg_rice':(1,'จาน',{}),'bubble_tea':(1,'แก้ว',{}),
 **{ident:(1,'จาน',{}) for ident in ('pork_leg_rice','omelette_rice','fried_chicken_rice','fried_rice','pad_see_ew','chicken_noodles','macaroni','pad_thai','chicken_biryani','basil_chicken_egg','carbonara')},
 'plain_rice':(1,'ทัพพีเล็ก',{'ทัพพี':1,'ถ้วย':3}),
 'boiled_egg':(1,'ฟอง',{}),
 'whole_milk':(240,'มล.',{'กล่อง':240}),'skim_milk':(240,'มล.',{}),
 'lowfat_milk':(240,'มล.',{}),'unsweet_soy':(240,'มล.',{}),
 'tom_yum':(1,'ถ้วย',{}),'clear_tom_yum':(1,'ถ้วย',{}),'coconut_tom_yum':(1,'ถ้วย',{}),
}
for food in FOODS:
    if food['id'] in SERVINGS:
        qty,unit,conversions=SERVINGS[food['id']]
        food['serving']={'quantity':qty,'unit':unit,'unit_factors':conversions}

# Audited numeric facts only from DOH school-meal recipes, PDF pages 21–53.
# A source serving is the recipe for one person, not a standard adult plate.
RECIPE_FACTS=[
 ('stuffed_egg','ไข่ยัดไส้',181.6,21,'ส่วน',[]),
 ('son_in_law_egg','ไข่ลูกเขย',276.8,22,'ส่วน',[]),
 ('steamed_egg','ไข่ตุ๋นทรงเครื่อง',81.6,23,'ส่วน',[]),
 ('exploded_egg','ไข่ระเบิด',100.8,24,'ส่วน',[]),
 ('fermented_pork_omelette','ไข่เจียวแหนม',323.9,25,'ส่วน',[]),
 ('fried_egg_salad','ยำไข่ดาว',100.5,28,'ส่วน',[]),
 ('papaya_egg','มะละกอผัดไข่',152.1,30,'ส่วน',[]),
 ('bitter_melon_egg','มะระผัดไข่',111.3,31,'ส่วน',[]),
 ('cucumber_egg','แตงกวาผัดไข่',111.3,33,'ส่วน',[]),
 ('gourd_egg','บวบผัดไข่',112.3,34,'ส่วน',[]),
 ('mushroom_egg','เห็ดหูหนูผัดไข่',127.3,35,'ส่วน',[]),
 ('bamboo_egg','หน่อไม้ผัดไข่',118.7,36,'ส่วน',[]),
 ('pickled_cabbage_egg','ผักกาดดองผัดไข่',140.2,37,'ส่วน',[]),
 ('glass_noodle_egg','ผัดวุ้นเส้นใส่ไข่',212.8,38,'ส่วน',[]),
 ('bitter_melon_stuffed_egg','มะระยัดไส้ไข่',238.5,39,'ส่วน',[]),
 ('egg_soup','แกงจืดไข่น้ำ',223.4,41,'ส่วน',['ต้มจืดไข่น้ำ']),
 ('egg_palo','ไข่พะโล้',352.9,42,'ส่วน',[]),
 ('pad_thai_egg_wrap','ผัดไทยห่อไข่',603.3,45,'จาน',['ผัดไทห่อไข่']),
 ('topped_fried_egg_rice','ข้าวไข่ดาวทรงเครื่อง',683.38,46,'จาน',[]),
 ('shrimp_paste_rice','ข้าวคลุกกะปิ',463,47,'จาน',['ข้าวคลุกกะปิหมูหวาน','ข้าวคลุกกะปิไก่หวาน']),
 ('southern_noodles','ขนมจีนน้ำยาปักษ์ใต้',346.8,49,'จาน',[]),
 ('curry_noodles','ขนมจีนน้ำยา',370,50,'จาน',[]),
 ('red_pork_egg_rice','ข้าวหมูแดงไข่ต้ม',351.1,51,'จาน',['ข้าวหมูแดงใส่ไข่ต้ม']),
 ('vietnamese_noodles','กวยจั๊บญวน',272.9,52,'ชาม',['ก๋วยจั๊บญวน']),
 ('seafood_suki','สุกี้น้ำทะเล',235.4,53,'ชาม',['สุกี้ทะเลน้ำ']),
]
for ident,name,kcal,page,unit,aliases in RECIPE_FACTS:
    FOODS.append({'id':ident,'name':name,'aliases':aliases,'kcal':[kcal,kcal],
        'basis':f'1 {unit} ตามสูตรอาหารสำหรับ 1 คนในเอกสารอาหารเด็กวัยเรียน',
        'url':RICE,'published':None,'publisher':'สำนักโภชนาการ กรมอนามัย',
        'location':f'PDF หน้า {page} ตารางคุณค่าทางโภชนาการสำหรับ 1 คน',
        'serving':{'quantity':1,'unit':unit,'unit_factors':{}},
        'note':'เป็นสูตรและปริมาณสำหรับเด็กวัยเรียน ไม่ใช่จานมาตรฐานผู้ใหญ่หรือทุกสูตรตามร้าน; ไม่รวมข้าวเพิ่มหรือเครื่องเคียงนอกสูตร'})
# Previously this dish had an unscalable news figure. Use the independently
# verified recipe serving, preserving the earlier reference for audit.
pumpkin=next(f for f in FOODS if f['id']=='pumpkin_egg')
pumpkin.update(kcal=[145.3,145.3],url=RICE,published=None,
    basis='1 ส่วนตามสูตรอาหารสำหรับ 1 คนในเอกสารอาหารเด็กวัยเรียน',
    location='PDF หน้า 32 ตารางคุณค่าทางโภชนาการสำหรับ 1 คน',
    serving={'quantity':1,'unit':'ส่วน','unit_factors':{}},
    note='สูตรเด็กวัยเรียน ไม่รวมข้าว; ข่าวเดิมให้ 118 kcal แต่ไม่ระบุหน่วย จึงไม่ใช้ตัวเลขนั้นรวมยอด',
    prior_reference={'url':EGG,'kcal':[118,118],'serving_unknown':True})
for ident,name,quantity,unit,aliases in [
 ('ripe_mango','มะม่วงสุก',.5,'ผลเล็ก',[]),('green_mango','มะม่วงดิบ',1,'ผลเล็ก',[]),
 ('grapes','องุ่น',15,'ผลเล็ก',[]),('cantaloupe','แคนตาลูป',1/3,'ผล',[]),
 ('plain_rice_soup','ข้าวต้มเปล่า',2,'ทัพพีเล็ก',[]),('plain_rice_noodles','ขนมจีนเปล่า',1.5,'จับ',['เส้นขนมจีน']),
]:
    kcal=60 if ident in ('ripe_mango','green_mango','grapes','cantaloupe') else 80
    factors={'ผล':1,'ลูก':1} if unit=='ผลเล็ก' else {'ลูก':1} if unit=='ผล' else {'ทัพพี':1} if unit=='ทัพพีเล็ก' else {}
    FOODS.append({'id':ident,'name':name,'aliases':aliases,'kcal':[kcal,kcal],
        'basis':f'{quantity:g} {unit} ตามอาหารแลกเปลี่ยน','url':SIRIRAJ_EXCHANGE,'published':None,
        'publisher':'ฝ่ายโภชนาการ โรงพยาบาลศิริราช','location':'หมวดอาหารแลกเปลี่ยน ข้าว–แป้ง / ผลไม้',
        'serving':{'quantity':quantity,'unit':unit,'unit_factors':factors},
        'note':'ใช้เฉพาะปริมาณและขนาดอ้างอิง ไม่รวมเครื่องจิ้ม น้ำตาล น้ำแกงหรือกับข้าว'})
# Selected numeric facts from measured Thai dishes, not a copy of the table.
# The 2008 study weighed each sampled plate; grams apply to that recipe only.
THAI_DISH_STUDY='https://nutrition2.anamai.moph.go.th/th/research2/download?did=25214&id=78322&lang=th&mid=35886&mkey=m_document'
THAI_DISH_FACTS=[
 ('green_curry_chicken_rice','ข้าวราดแกงเขียวหวานไก่',278,313,6,True,[]),
 ('panaeng_pork_rice','ข้าวราดแกงพะแนงหมู',288,393,6,True,['ข้าวพะแนงหมู']),
 ('massaman_chicken_rice','ข้าวราดแกงมัสมั่นไก่',353,487,6,True,[]),
 ('sour_vegetable_curry_rice','ข้าวราดแกงส้มผักรวม',371,315,6,True,[]),
 ('minced_pork_omelette_rice','ข้าวราดไข่เจียวหมูสับ',342,808,6,True,['ข้าวไข่เจียวหมูสับ']),
 ('tofu_pork_soup_rice','ข้าวราดต้มจืดเต้าหู้หมูสับ',473,263,6,True,[]),
 ('palo_pork_egg_rice','ข้าวราดต้มหมูพะโล้กับไข่',338,535,6,True,[]),
 ('basil_chicken_rice','ข้าวราดผัดกระเพราไก่',270,469,6,True,['ข้าวกะเพราไก่','ข้าวกระเพราไก่','ข้าวราดผัดกะเพราไก่']),
 ('kale_crispy_pork_rice','ข้าวราดผัดคะน้าหมูกรอบ',331,546,6,True,['ข้าวคะน้าหมูกรอบ']),
 ('mixed_vegetable_rice','ข้าวราดผัดผักรวม',282,332,7,True,['ข้าวผัดผักรวม']),
 ('garlic_pork_rice','ข้าวราดหมูทอดกระเทียม',228,441,7,True,['ข้าวหมูทอดกระเทียม']),
 ('fried_egg_salad_rice','ข้าวราดยำไข่ดาว',366,638,7,True,[]),
 ('braised_beef_soup','เกาเหลาเนื้อตุ๋น',310,149,7,False,[]),
 ('pork_soup','เกาเหลาหมู',506,163,7,False,[]),
 ('liang_curry','แกงเลียง',392,119,7,False,[]),
 ('catfish_larb','ลาบปลาดุก',109,167,7,False,[]),
 ('pork_blood_soup','ต้มเลือดหมู',600,216,7,False,[]),
 ('beef_soup','ซุปเนื้อวัว',443,214,7,False,[]),
 ('mackerel_three_flavours','ปลาทู 3 รส',136,203,7,False,['ปลาทูสามรส']),
 ('wonton_soup','เกี๊ยวน้ำ',523,141,8,False,[]),
 ('wonton_red_pork_noodles','บะหมี่เกี๊ยวหมูแดง',485,332,8,False,[]),
 ('dry_pork_noodles','บะหมี่แห้งหมู',244,463,8,False,[]),
 ('rolled_noodles_thick_soup','ก๋วยจั๊บน้ำข้น',553,368,8,False,[]),
 ('rice_noodles_northern','ขนมจีนน้ำเงี้ยว',480,308,8,False,[]),
 ('rice_noodles_green_curry','ขนมจีนแกงเขียวหวาน',370,416,8,False,[]),
 ('pork_fried_rice','ข้าวผัดหมู',315,581,9,True,[]),
 ('red_pork_rice','ข้าวหมูแดงราดน้ำ',352,521,9,True,['ข้าวหมูแดง']),
 ('roast_pork_rice','ข้าวหมูอบ',248,432,9,True,[]),
 ('shrimp_pad_thai','ผัดไทยกุ้งสด',281,486,9,False,['ผัดไทกุ้งสด']),
 ('chicken_suki_soup','สุกี้ไก่น้ำ',540,253,9,False,['สุกี้น้ำไก่']),
 ('mixed_suki_soup','สุกี้รวมมิตรน้ำ',530,207,9,False,['สุกี้น้ำรวมมิตร']),
 ('mixed_suki_dry','สุกี้รวมมิตรแห้ง',384,399,9,False,['สุกี้แห้งรวมมิตร']),
 ('pork_rad_na','เส้นใหญ่ราดหน้าหมู',450,506,9,False,['ราดหน้าหมูเส้นใหญ่']),
 ('oyster_omelette','หอยทอด',261,812,9,False,[]),
]
for ident,name,grams,kcal,page,includes_rice,aliases in THAI_DISH_FACTS:
    unit='จาน' if includes_rice or ident in ('pork_rad_na','shrimp_pad_thai','oyster_omelette','dry_pork_noodles') else 'ส่วน'
    FOODS.append({'id':ident,'name':name,'aliases':aliases,'kcal':[kcal,kcal],
        'basis':f'1 จานตัวอย่าง น้ำหนัก {grams} กรัม ในรายงานปี 2551'+(' รวมข้าวแล้ว' if includes_rice else ''),
        'url':THAI_DISH_STUDY,'published':'2008','publisher':'กองโภชนาการ กรมอนามัย',
        'location':f'PDF หน้า {page} ตารางที่ 1 คอลัมน์น้ำหนัก/จาน และพลังงาน',
        'serving':{'quantity':1,'unit':unit,'unit_factors':{'กรัม':1/grams,**({'จาน':1} if unit=='ส่วน' else {})}},
        'includes_rice':includes_rice,'sample_weight_g':grams,
        'note':'ค่าจากจานตัวอย่างที่ศึกษาปี 2551 ไม่ใช่ทุกสูตรตามร้าน; น้ำหนักและน้ำมันจริงอาจต่างกัน ไม่แปลงถ้วยเป็นจานเอง'})

# A generic plain-milk query is explicitly a range over the existing cited
# cow-milk types. Never map sweetened/condensed/plant milk to low-fat milk.
FOODS.append({'id':'unspecified_plain_milk','name':'นมจืดไม่ระบุไขมัน','aliases':['นม','นมจืด','นมวัว'],
    'kcal':[90,150],'basis':'นมวัวจืด 240 มล. ช่วงนมขาดมันเนยถึงไขมันเต็ม',
    'url':CMU_MILK,'additional_sources':[{'url':SIRIRAJ_EXCHANGE,'publisher':'ศิริราชพยาบาล มหาวิทยาลัยมหิดล'}],
    'published':None,'publisher':'ศูนย์ศรีพัฒน์ คณะแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่',
    'location':'อาหารแลกเปลี่ยน หมวดนม: ขาดมันเนย 90 / พร่องมันเนย 120 kcal ต่อ 240 มล.; ไขมันเต็ม 150 จากศิริราช',
    'serving':{'quantity':240,'unit':'มล.','unit_factors':{}},
    'note':'ตีความคำว่านมเป็นนมวัวจืด ยังไม่ทราบไขมันจึงแสดงช่วง ไม่ใช่ค่าเดียวกับนมพร่องมันเนย; ไม่ใช้กับนมปรุงรส นมข้น หรือนมพืช ตรวจฉลากและแก้ชนิดให้ตรง'})

next(f for f in FOODS if f['id']=='shrimp_pad_thai')['note']+='; แหล่งอ้างอิงไม่รวมผักสดแนม'

# Spelling aliases preserve the recipe and ingredients; no substring/fuzzy
# match that would turn a fried dish into a boiled dish or invent an add-on.
for food in FOODS:
    variants=[]
    for name in [food['name'],*food['aliases']]:
        if 'กะเพรา' in name:variants.append(name.replace('กะเพรา','กระเพรา'))
    food['aliases']=list(dict.fromkeys([*food['aliases'],*(n for n in variants if n!=food['name'])]))

def food_reference(name):
    import re
    cleaned=re.sub(r'\s+','',name or '')
    # Only exact dish names; ข้าวมันไก่ทอด is not ข้าวมันไก่ต้ม.
    food=next((f for f in FOODS if cleaned in [re.sub(r'\s+','',x) for x in [f['name'],*f['aliases']]]),None)
    if not food:return {'name':name,'status':'unknown','kcal':None,'actual_consumed_kcal':None,'note':'ยังไม่มีค่าพลังงานที่ตรวจแหล่งและหน่วยเสิร์ฟได้สำหรับเมนูนี้'}
    return dict(food,status='reference_only',actual_consumed_kcal=None,accessed_at='2026-10-12',publisher=food.get('publisher','กรมอนามัย'),health_score=None)

# Proposed preparations, with an explicit ingredient whitelist. Condiments are
# kept plain; all kitchens still require ingredient/cross-contact verification.
MENUS=[
 {'id':'chicken_veg_rice','name':'ข้าว + ไก่ต้มไม่ติดหนัง + ผักต้ม','ingredients':['ข้าว','ไก่','ผัก','เกลือ'],'contains':['ไก่'],'tags':['ต้ม','โปรตีน','ผัก'],'note':'แยกน้ำจิ้ม เลือกผักที่กินได้'},
 {'id':'fish_veg_rice','name':'ข้าว + ปลานึ่ง + ผักต้ม','ingredients':['ข้าว','ปลา','ผัก','เกลือ'],'contains':['ปลา'],'tags':['นึ่ง','โปรตีน','ผัก'],'note':'ตรวจชนิดปลาและเครื่องปรุงก่อนกิน'},
 {'id':'tofu_veg_rice','name':'ข้าว + เต้าหู้ผัดผักน้ำมันน้อย','ingredients':['ข้าว','ถั่วเหลือง','ผัก','น้ำมัน','เกลือ'],'contains':['ถั่วเหลือง'],'tags':['มังสวิรัติ','โปรตีน','ผัก'],'note':'ใช้เต้าหู้ถั่วเหลืองและไม่เติมซอสที่ไม่ทราบส่วนผสม'},
 {'id':'egg_veg_rice','name':'ข้าว + ไข่ตุ๋นใส่ผัก','ingredients':['ข้าว','ไข่','ผัก','น้ำ','เกลือ'],'contains':['ไข่'],'tags':['นึ่ง','โปรตีน','ผัก'],'note':'ไม่เติมนม น้ำซุป หรือซอสโดยไม่ตรวจส่วนผสม'},
 {'id':'chicken_salad_rice','name':'สลัดผัก + ไก่ต้ม + ข้าว','ingredients':['ข้าว','ไก่','ผัก','มะนาว','น้ำมัน'],'contains':['ไก่'],'tags':['โปรตีน','ผัก','สลัด'],'note':'ใช้มะนาวและน้ำมันแทนน้ำสลัดสำเร็จรูป ไม่ใช่สลัดผักอย่างเดียว'},
 {'id':'pork_soup_rice','name':'ข้าว + แกงจืดหมูไม่ติดมันใส่ผัก','ingredients':['ข้าว','หมู','ผัก','น้ำ','เกลือ'],'contains':['หมู'],'tags':['ต้ม','โปรตีน','ผัก'],'note':'ไม่ใช้ผงปรุงรสและไม่เติมซอสที่ไม่ทราบส่วนผสม'},
]
