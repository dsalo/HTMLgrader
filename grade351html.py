#!/usr/bin/python

'''Grades mechanics on LIS 351 HTML/CSS assignments:
		* checks existence of >=3 HTML files, one CSS file, >=1 image file
		* checks 
		* validates HTML files
			** checks for <nav> containing links to all other pages
			** checks that all pages have <title>s
			** checks for at least two levels of heading tags
			** checks for an external link
			** checks for a list (either <ol> or <ul>) and a paragraph
		* does (basic, somewhat inadequate) CSS validation
			** were margin, background-color, and font-family set on body?
			** "serif" used as font fallback?
			** headings sans-serif?
			
KNOWN BUGS:
	* Has trouble dealing with multiple CSS stylesheets
	* Can't test CSS-on-body if the selector used is an ID or class selector
	  rather than the body tag
'''

# note to self: 
#	pip3 install bs4
#	pip3 install tidylib (AND MAKE SURE you have the CURRENT Tidy installed)
#	pip3 install tinycss2
import glob, os, sys, shutil, html, re, string, zipfile, argparse, tinycss2
from bs4 import BeautifulSoup as bs
from tidylib import tidy_document

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--dir", help="Specify the directory containing zip files to be graded.")
	args = parser.parse_args()
	if args.dir:
		grading_dir = os.path.abspath(args.dir)
	else:
		grading_dir = os.path.abspath(os.curdir)
		
	grading_results = grade_the_things(grading_dir)
	outfile = os.path.join(grading_dir, 'Grading_Results.txt')
	with open(outfile, 'w') as f:
		f.write(grading_results)

	print("\n\nDone!")

def grade_the_things(grading_dir):

	files = []
	grading_results = ''
	for file in os.listdir(grading_dir):
		#some of these might be directories or other garbage
		#most will be zip files
		file = os.path.join(grading_dir, file) #otherwise it assumes current directory
		if os.path.isdir(file): continue
		else:
			path, fullfilename = os.path.split(file)
			filename, ext = os.path.splitext(fullfilename)
			if ext == ".zip":
				files.append(file)
			elif ext == ".DS_Store": continue #APPLE STAWP
			elif filename == ".DS_Store": continue
			elif fullfilename == "Grading_Results.txt": continue #ignore script reruns, please
			else: #throw a wtf
				print("\n\tFile %s is not a zip file; please assess." % file)

	print("Files processed.")
	
	files.sort()
	
	for file in files:
		file_grade = grade_zip(file).strip()
		if file_grade: grading_results = grading_results + file_grade + "\n\n" 
		else: grading_results = grading_results +  "%s all good.\n\n" % (file)
		
	print("All the things graded.")
	return grading_results


def grade_zip(inputfile):
	#check that the right files exist
	cssfiles = []
	htmlfiles = []
	imagefiles = []
	
	imageexts = [".jpg", ".jpeg", ".png", ".gif"]

	zipobj = zipfile.ZipFile(inputfile)
	zipinfo = zipfile.ZipInfo(inputfile)
	grading_result = ''

	sitefiles = []
	#get rid of Mac resource forks, other crap	
	for file in zipobj.namelist():
		filename, ext = os.path.splitext(file)
		if filename[0:2] == "__": continue #Apple resource forks, how much they suck
		elif filename[0] == ".": continue #.DS_Store also sucks
		else: sitefiles.append(file)
	print("\tSitefiles listed.")

	#do the file count/sort
	for file in sitefiles:
		filename, ext = os.path.splitext(file)

		if ext.lower() == ".html" or ext.lower() == ".htm":
			htmlfiles.append(file)
		elif ext.lower() == ".css": 
			cssfiles.append(file)
		elif ext.lower() in imageexts:
			imagefiles.append(file)
	print("\tSitefiles sorted.")
			
	if len(htmlfiles) < 4: grading_result = grading_result + "\n\tOnly %d HTML files." % (len(htmlfiles))
	if len(imagefiles) < 1: grading_result = grading_result + "\n\tDoes not have an image file."
	if len(cssfiles) < 1: grading_result = grading_result + "\n\tDoes not have a CSS file."
	if len(cssfiles) > 1: grading_result = grading_result + "\n\tContains more than one CSS file; investigate manually."
	print("\tFile types checked.")
		
	#HTML file checks
	extlinks = 0 #does the entire site contain at least one external link?
	headspresent = {'h1': 0, 'h2': 0, 'h3': 0, 'h4': 0, 'h5': 0, 'h6': 0}
	headerlevels = 0 #are there at least two different heading tags in the site?
	anylist = 0 #is there a list?
	anypara = 0 #is there a paragraph?

	for file in htmlfiles:
		#does it validate?
		document, errors = tidy_document(zipobj.read(file))
		errors = errors.strip()
		for error in errors.split("\n"):
			if error.strip(): grading_result = grading_result + "\n\t" + error.strip() #unreal extra whitespace from Tidy, why?
		
		#do the checks for individual bits of HTML
		soup = bs(zipobj.read(file), 'html.parser')
		check = check_htmlfile(soup, htmlfiles, imagefiles, cssfiles)
		if check.strip():
			grading_result = grading_result + "\n\t" + file + " HTML errors:" + check.strip()
		#only check for links, lists, paragraphs if they haven't already been found
		#in another HTML file
		if not extlinks:
			extlinks = check_extlinks(soup)
		if not anylist: anylist = check_for_list(soup)
		if not anypara: anypara = check_for_paragraphs(soup)
		headspresent = check_for_headers(soup, headspresent)
	print("\tHTML files validated.")
		
	if not extlinks: grading_result = grading_result + "\n\tNo external links anywhere in site."
	if not anylist: grading_result = grading_result + "\n\tNo list anywhere in site."
	if not anypara: grading_result = grading_result + "\n\tNo paragraph anywhere in site."

	#evaluate the headspresent dictionary to see if we have two levels of heads
	#(can't do this file-by-file because the different <h#> tags may be in different files)
	for value in headspresent.values():
		#each value in dictionary is "how many <h#> tags did we find in this file?"
		#only increment if the number for a given <h#> is more than 0
		if value > 0: headerlevels = headerlevels + 1
	if headerlevels < 2:
		grading_result = grading_result + "\n\tSite does not have two levels of heading tags."
		
	print("\tHTML features graded.")
	
	#CSS file check
	if cssfiles:
		for cssfile in cssfiles:
			print ("\tCSS file: " + cssfile)
			check = check_css(zipobj.read(cssfile))
			print("\tCSS file %s read." % (cssfile))
			if check.strip():
				grading_result = grading_result + "\n\n\t" + cssfile + " CSS errors:" + check
		print("\tCSS files graded.")
			
	print("Graded %s" % (inputfile))
	
	if grading_result.strip(): 
		grading_result = "\nFile: %s\n" % zipinfo.filename + grading_result

	return grading_result
	
def check_extlinks(soup):
	#is there an external link?
	extlinks = 0
	links = soup.find_all("a")
	for link in links:
		try:
			target = link['href']
		except:
			pass #ignoring KeyError, assuming somebody did <a name> or <a id>
		else:
			if target[0:4] == "http": 
				extlinks = 1
				break #sorta hacky, but okay
	
	return extlinks

def check_for_list(soup):
	anylist = 0
	if soup.select("ul"): anylist = 1
	elif soup.select("ol"): anylist = 1
	
	return anylist

def check_for_headers(soup, headspresent):
	if soup.select("h1"): headspresent['h1'] = 1
	if soup.select("h2"): headspresent['h2'] = 1
	if soup.select("h3"): headspresent['h3'] = 1
	if soup.select("h4"): headspresent['h4'] = 1
	if soup.select("h5"): headspresent['h5'] = 1
	if soup.select("h6"): headspresent['h6'] = 1
	return headspresent

def check_for_paragraphs(soup):
	anypara = 0
	
	if soup.select("p"): anypara = 1

	return anypara

def check_htmlfile(soup, htmlfiles, imagefiles, cssfiles):
	linknames = []
	srcnames = []
	result = ''
	for file in htmlfiles:
		path, filename = os.path.split(file)
		linknames.append(filename.lower()) #utterly not dealing with filename case problems

	for file in imagefiles:
		path, filename = os.path.split(file)
		srcnames.append(filename.lower())
		
	#does it have a <title>?
	if not soup.title:
		result = result + "\n\tNo <title> element."
	#does it have a <nav>?
	if not soup.select("nav"):
		result = result + "\n\tNo <nav> element."
	else:
	#do the navlinks work?
		navlinks = soup.select("nav a")
		if not navlinks:
			result = result + "\n\t<nav> element contains no links."
		else:
			for link in soup.select("nav a"):
				try:
					href = link['href'].lower()
				except KeyError:
					result = result + "\n\tProblematic nav link: %s" % (link)
				else:
					if href not in linknames and href[0:4] != 'http': 
						result = result + "\n\tBroken nav link: %s" % (link['href'])

	#does the <link> to the css file work? 
	#(assuming there is a CSS file; if not, that gets caught elsewhere)
	if cssfiles:
		for cssfile in cssfiles:
			path, cssfilename = os.path.split(cssfile)
			if not soup.link:
				result = result + "\n\tNo <link> to CSS."
			else:
				#Google Fonts is apparently using a CSS <link> these days...
				#it's fine, shouldn't count against the student
				csshref = kill_dirs(soup.link['href'])
				if csshref != cssfilename and csshref.find("css?family") == -1: 
					result = result + "\n\tCSS <link> doesn't work: %s %s" % (soup.link['href'], cssfilename)
	
	images = soup.find_all("img")
	#do image calls work?
	for image in images:
		source = kill_dirs(image['src'].lower())
		if source not in srcnames:
			if source[0:4] == "http": continue #we're letting hotlinks pass
			else: result = result + "\n\tImage file %s called but appears not to exist." % (image['src'])
		#is there alt text on the image?
		try:
			alt = image['alt']
		except KeyError:
			result = result + "\n\tNo alt text: %s" % (image)

	#see if any <body> tags have a class or id;
	#if so, warn to check CSS manually for margin/font settings
	#TODO: rewrite check_css to account for this
	try:
		bodyclass = soup.body['class']
	except: pass
	else: result = result + "\n\n<body> has class %s; check CSS manually." % bodyclass
	
	try:
		bodyid = soup.body['id']
	except: pass
	else: result = result + "\n\t<body> has id %s; check CSS manually." % bodyid
	
	return result

def check_css(filestream):
	result = ''
	#did they change the margin on <body>?
	marginpresent = 0
	#did they change the background color on <body>?
	backgroundchanged = 0
	#did they change something to serif, something else to sans-serif?
	serif = 0
	sansserif = 0

	css, encoding = tinycss2.parse_stylesheet_bytes(filestream, skip_comments=1, skip_whitespace=1)
	# A list of QualifiedRule, AtRule, Comment (if skip_comments is false), 
	# WhitespaceToken (if skip_whitespace is false), and ParseError objects.
	
	allselectors = []
	allproperties = [] 
	
	parseerrors = [x for x in css if x.type == 'error']
	for error in parseerrors:
		result = result + "\n\tCSS parsing error line %s: %s" % (error.source_line, error.message)
	qualrules = [x for x in css if x.type == 'qualified-rule']

	for qualrule in qualrules:
		#node.prelude and node.content are both lists of objects
		#kill the useless whitespace nodes out of them
		try: selectors = [x for x in qualrule.prelude if x.type != 'whitespace']
		except ValueError: selectors = qualrule.prelude
		try: rules = [x for x in qualrule.content if x.type != 'whitespace']
		except ValueError: rules = qualrule.content
		for rule in rules:
			if rule.type == 'function' or rule.type == 'literal': continue
			if rule.value not in allproperties: allproperties.append(rule.value)
		for selector in selectors:
			if selector.type != 'ident': continue
			if selector.value not in allselectors: allselectors.append(selector.value)

		for selector in selectors:
			if selector.type == 'ident':
				if selector.value == 'body' or selector.value == 'html':
					for rule in rules:
						if rule.type == 'ident':
							#either margin or padding is okay; slice means they're okay if they used margin-top etc.
							if rule.value[0:6] == 'margin' or rule.value[0:7] == 'padding': marginpresent = 1
							if rule.value[0:10] == 'background': backgroundchanged = 1
	
	if 'serif' not in allproperties: result = result + "\n\tNo font changed to serif anywhere."
	if 'sans-serif' not in allproperties: result = result + "\n\tNo font changed to sans-serif anywhere."
	print("\tCSS validation complete.")
	if not marginpresent: result = result + "\n\tNo margin on <body>."	
	if not backgroundchanged: result = result + "\n\tBackground color/image not changed."
	return result

def kill_dirs(filename):
	#if they used a subfolder for images or CSS or anything,
	#filename comparisons inside the zip file break
	dir, sep, filename = filename.rpartition("/")
	
	return filename
	
def opener(path, flags):
	dir_fd = os.open(os.curdir(), os.O_RDONLY)
	return os.open(path, flags, dir_fd = dir_fd)

def finish_up(grading_results):
	#write out the grading results to a file
	with open(os.path.join(dir_fd, 'Grading_Results.txt'), 'w', opener=opener) as f:
		print(grading_results, file=f)
	
	#declare victory
	print("Wrote file: Grading_Results.txt")

if __name__ == "__main__": main()
