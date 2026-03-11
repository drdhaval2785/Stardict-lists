import json
import csv
import os
import urllib.request
import re
import iso639

def parse_freedict(file_path):
    """
    Parses the freedict-database.json file from freedict.org and extracts StarDict links.
    """
    url = 'https://freedict.org/freedict-database.json'
    print(f"Fetching {url}")
    with urllib.request.urlopen(url) as response:
        data = json.load(response)
    
    results = []
    
    for entry in data:
        # Rule 4: name should be expanded to 'afr-deu freedict' instead of 'afr-deu'
        original_name = entry.get('name', '')
        if not original_name:
            continue
            
        expanded_name = f"{original_name} freedict"
        
        # Rule 5: Source Language is 'afr' and Target language is 'deu' in case the name is 'afr-deu'
        parts = original_name.split('-')
        if len(parts) == 2:
            src_lang, tgt_lang = parts
        else:
            # Fallback if name is not standard
            src_lang = entry.get('sourceLanguage', '')
            tgt_lang = entry.get('targetLanguage', '')
            
        # Rule 6: keep URL to only "stardict" platform
        stardict_release = None
        for release in entry.get('releases', []):
            if release.get('platform') == 'stardict':
                stardict_release = release
                break
                
        # If there is no stardict platform release, we skip or handle accordingly (Link is mandatory)
        if not stardict_release:
            print(f"Skipping '{original_name}': No 'stardict' release found.")
            continue
            
        link = stardict_release.get('URL', '')
        # Mandatory fields check
        if not src_lang or not tgt_lang or not expanded_name or not link:
            missing = [f for f, v in zip(["Source", "Target", "Name", "Link"], [src_lang, tgt_lang, expanded_name, link]) if not v]
            print(f"Skipping '{original_name}': Missing mandatory fields - {', '.join(missing)}")
            continue
            
        # Optional fields
        headword_count = entry.get('headwords', '')
        version = stardict_release.get('version', entry.get('edition', ''))
        date = stardict_release.get('date', entry.get('date', ''))
        
        results.append({
            'Source': src_lang,
            'Target': tgt_lang,
            'Name': expanded_name,
            'Link': link,
            'HeadwordCount': headword_count,
            'Version': version,
            'Date': date
        })
        
    return results

def normalize_lang(lang):
    """
    Normalizes 2-letter or friendly names to 3-letter ISO codes as per user requirements.
    """
    if not lang:
        return ''
    mapping = {
        'sa': 'san', 'german': 'deu', 'french': 'fra', 'en': 'eng', 'hi': 'hin',
        'prakrit': 'pra', 'pali': 'pli', 'pi': 'pli', 'ne': 'nep', 'pa': 'pan',
        'gu': 'guj', 'ks': 'kas', 'ur': 'urd', 'ma': 'mar', 'or': 'ori',
        'as': 'asm', 'bn': 'ben', 'dv': 'dra', 'kn': 'kan', 'ta': 'tam',
        'ml': 'mal', 'si': 'sin', 'te': 'tel', 'bo': 'bod'
    }
    return mapping.get(lang.lower(), lang.lower())

def parse_tars_md(url):
    """
    Fetches the given tars.MD url and parses its tar.gz links to extract dictionary metadata.
    """
    results = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
        return results

    # Find all download links ending with .tar.gz (optionally inside < >)
    link_pattern = re.compile(r'<?(https?://[^\s">]+\.tar\.gz)>?')
    links = link_pattern.findall(content)
    
    repo_to_code = {
        'sanskrit': 'san', 'hindi': 'hin', 'marathi': 'mar', 'gujarati': 'guj',
        'nepali': 'nep', 'panjabi': 'pan', 'oriya': 'ori', 'assamese': 'asm',
        'bengali': 'ben', 'kannada': 'kan', 'tamil': 'tam', 'malayalam': 'mal',
        'sinhala': 'sin', 'telugu': 'tel', 'urdu': 'urd', 'kashmiri': 'kas',
        'tibetan': 'bod', 'english': 'eng', 'pali': 'pli', 'prakrit': 'pra',
        'ayurveda': 'san', 'divehi': 'dra'
    }

    for link in links:
        parts = link.split('/')
        if len(parts) < 4:
            continue
            
        repo_name = ''
        if 'github.com' in link or 'githubusercontent.com' in link:
            if len(parts) >= 5:
                repo_name = parts[4].replace('stardict-', '')
        elif 'archive.org' in link:
            # For archive.org links, repo name might be in the path
            repo_name = 'archive'
            for part in parts:
                if 'english' in part: repo_name = 'english'; break
                if 'sanskrit' in part: repo_name = 'sanskrit'; break
            
        filename = parts[-1]
        
        # Parse Source and Target from URL path
        src_lang = ''
        tgt_lang = ''
        
        for part in parts:
            if part.endswith('-head'):
                src_lang = part.replace('-head', '').split('_')[0]
            elif part.endswith('-entries'):
                tgt_lang = part.replace('-entries', '').split('_')[0]
        
        # Infer from repo name if fields are still missing
        default_lang = ''
        if repo_name:
            # First check if repo_name itself maps directly to a code
            for key, code in repo_to_code.items():
                if key in repo_name:
                    default_lang = code
                    break
        
        if not src_lang:
            src_lang = default_lang
        if not tgt_lang:
            tgt_lang = default_lang

        # Normalize to 3-letter codes
        src_lang = normalize_lang(src_lang)
        tgt_lang = normalize_lang(tgt_lang)
                
        # Parse Name and Date from filename
        name = ''
        date = ''
        if '__' in filename:
            file_parts = filename.split('__')
            name = file_parts[0]
            date_str = file_parts[1]
            date = date_str[:10] if len(date_str) >= 10 else date_str
        else:
            name = filename.replace('.tar.gz', '')
        
        # Custom Rules
        # 2. 'apte-hi', 'vedic-tituals_hi' have 'hin' as target.
        if name in ['apte-hi', 'vedic-rituals-hi', 'vedic-tituals_hi']:
            tgt_lang = 'hin'
        # 3. samskritam-tamizham_dictionary has 'tam' as target.
        if name == 'samskritam-tamizham_dictionary':
            tgt_lang = 'tam'
        # 4. 'shabdArtha_kaustubha' has 'tel' as target.
        if name == 'shabdArtha_kaustubha':
            tgt_lang = 'tel'
        # 5. 'bopp' has 'lat' as target.
        if name == 'bopp':
            tgt_lang = 'lat'
        # 9. LewissAnElementaryLatinDictionary is 'lat' to 'eng'
        if name == 'LewissAnElementaryLatinDictionary':
            src_lang = 'lat'
            tgt_lang = 'eng'
        # 10. MiddleLiddell and greek-analyses-unicode-babylon are from 'ell' to 'eng'
        if name in ['MiddleLiddell', 'greek-analyses-unicode-babylon']:
            src_lang = 'ell'
            tgt_lang = 'eng'
        # 11. subbarAya_en-kn is 'eng' to 'kan'
        if name == 'subbarAya_en-kn':
            src_lang = 'eng'
            tgt_lang = 'kan'
        # 7. All four dictionaries of 'pali-en' source has 'pli' as source and 'eng' as target
        if 'pali-en' in link:
            src_lang = 'pli'
            tgt_lang = 'eng'
        # 8. 'saad_dev' is from 'eng' to 'guj'
        if name == 'saad_dev':
            src_lang = 'eng'
            tgt_lang = 'guj'
        # 12. berntsen, molesworth and vaze are 'mar' to 'eng'
        if name in ['berntsen', 'molesworth', 'vaze']:
            tgt_lang = 'eng'

        # 6. 'frish' has 'rus', 'cze' and 'eng' as target. Create three entries.
        if name == 'frish':
            for t_lang in ['rus', 'cze', 'eng']:
                results.append({
                    'Source': src_lang,
                    'Target': t_lang,
                    'Name': name,
                    'Link': link,
                    'HeadwordCount': '',
                    'Version': '',
                    'Date': date
                })
            continue

        # Mandatory fields check
        if not src_lang or not tgt_lang or not name or not link:
            missing = [f for f, v in zip(["Source", "Target", "Name", "Link"], [src_lang, tgt_lang, name, link]) if not v]
            print(f"Skipping '{filename}' from {repo_name or url}: Missing mandatory fields - {', '.join(missing)}")
            continue
            
        results.append({
            'Source': src_lang,
            'Target': tgt_lang,
            'Name': name,
            'Link': link,
            'HeadwordCount': '',
            'Version': '',
            'Date': date
        })
        
    print(f"Successfully extracted {len(results)} entries from {url}")
    return results

def parse_dictionary_indices(file_path):
    """
    Parses the dictionaryIndices.md file from GitHub and processes each tars.MD URL.
    """
    url = 'https://github.com/indic-dict/stardict-index/raw/refs/heads/master/dictionaryIndices.md'
    print(f"Fetching {url}")
    with urllib.request.urlopen(url) as response:
        content = response.read().decode('utf-8')
    
    url_pattern = re.compile(r'<(https://raw\.githubusercontent\.com/indic-dict/[^>]*tars.*\.MD)>')
    urls = url_pattern.findall(content)
    
    results = []
    for url in urls:
        print(f"Fetching from {url}")
        rows = parse_tars_md(url)
        results.extend(rows)
        
    print(f"Total entries from dictionaryIndices.md: {len(results)}")
    return results

def parse_wiktionary(file_path):
    """
    Parses the Vuizur/Wiktionary-Dictionaries repository from GitHub API.
    Since we don't have a local file for this, we fetch directly from the repo.
    """
    results = []
    
    # We will try importing iso639, if not present we fall back to a minimal mapping
    try:
        from iso639 import Lang
        has_iso639 = True
    except ImportError:
        has_iso639 = False
        print("iso639-lang not installed. Using rudimentary mapping for Wiktionary languages.")

    # Minimal manual mapping for iso639 misses and common fallbacks
    manual_mapping = {
        'ancient greek': 'grc',
        'serbo-croatian': 'hbs',
        'alemannic german': 'gsw',
        'bavarian': 'bar',
        'middle english': 'enm',
        'old english': 'ang',
        'middle french': 'frm',
        'old french': 'fro',
        'romani': 'rom',
        'abkhaz': 'abk',
        'aramaic': 'arc',
        'avar': 'ava',
        'bikol central': 'bcl',
        'bourguignon': 'bgn',
        'brunei malay': 'kxd',
        'buryat': 'bua',
        'cantonese': 'yue',
        'central franconian': 'gmw',
        'dupaningan agta': 'duo',
        'east central german': 'deu',
        'franco-provençal': 'frp',
        'fula': 'ful',
        "ge'ez": 'gez',
        'german low german': 'nds',
        'greek': 'ell',
        'guaraní': 'grn',
        'ilocano': 'ilo',
        'interlingua': 'ina',
        'jeju': 'jje',
        'livonian': 'liv',
        'louisiana creole french': 'lou',
        'mandarin': 'cmn',
        'mauritian creole': 'mfe',
        'middle dutch': 'dum',
        'middle irish': 'mga',
        'middle korean': 'okm',
        'min nan': 'nan',
        'nivkh': 'niv',
        'norman': 'nrf',
        'north frisian': 'frr',
        'northern ndebele': 'nde',
        'occitan': 'oci',
        'ojibwe': 'oji',
        'okinawan': 'ryu',
        'old armenian': 'xcl',
        'old east slavic': 'orv',
        'old high german': 'goh',
        'old irish': 'sga',
        'old javanese': 'kaw',
        'old occitan': 'pro',
        'old polish': 'opl',
        'old portuguese': 'opt',
        'old swedish': 'osw',
        'ottoman turkish': 'ota',
        'papiamentu': 'pap',
        'phuthi': 'pdt',
        'piedmontese': 'pms',
        'proto-brythonic': 'brt-pro',
        'proto-celtic': 'cel-pro',
        'proto-finnic': 'fiu-pro',
        'proto-germanic': 'gem-pro',
        'proto-indo-european': 'ine-pro',
        'proto-indo-iranian': 'iir-pro',
        'proto-italic': 'itc-pro',
        'proto-malayo-polynesian': 'poz-pro',
        'proto-samic': 'smi-pro',
        'proto-slavic': 'sla-pro',
        'proto-turkic': 'trk-pro',
        'proto-west germanic': 'gmw-pro',
        'romansch': 'roh',
        'rwanda-rundi': 'kin',
        'sambali': 'xsb',
        'saterland frisian': 'stq',
        'slovene': 'slv',
        'sotho': 'sot',
        'south levantine arabic': 'ajp',
        'southern ndebele': 'nbl',
        'swazi': 'ssw',
        'taos': 'twf',
        'tarantino': 'taz',
        'tocharian a': 'xto',
        'tocharian b': 'txb',
        'tokelauan': 'tkl',
        'translingual': 'zxx',
        'tuvan': 'tyv',
        'vilamovian': 'wym',
        'waray-waray': 'war',
        'west frisian': 'fry',
        'westrobothnian': 'gmq-jrt'
    }

    def get_iso_code(lang_name):
        lower_name = lang_name.lower()
        if lower_name in manual_mapping:
            return manual_mapping[lower_name]
        
        if has_iso639:
            try:
                lang = Lang(lang_name)
                return lang.pt3  # 3-letter code
            except Exception:
                pass
        
        # Fallback to normalized if nothing found
        return normalize_lang(lang_name)

    url = "https://api.github.com/repos/Vuizur/Wiktionary-Dictionaries/contents/"
    print(f"Fetching from {url}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')
            data = json.loads(content)
    except Exception as e:
        print(f"Error fetching Wiktionary repositories: {e}")
        return results

    for item in data:
        name = item.get('name', '')
        if name.endswith(" Wiktionary dictionary stardict.tar.gz"):
            download_url = item.get('download_url', '')
            langs = name.replace(" Wiktionary dictionary stardict.tar.gz", "")
            
            parts = langs.split("-")
            if len(parts) >= 2:
                target_str = parts[-1]
                source_str = "-".join(parts[:-1])
                
                src_lang = get_iso_code(source_str)
                tgt_lang = get_iso_code(target_str)
                
                if not src_lang or not tgt_lang or not download_url:
                    missing = [f for f, v in zip(["Source", "Target", "Link"], [src_lang, tgt_lang, download_url]) if not v]
                    print(f"Skipping '{name}': Missing fields - {', '.join(missing)}")
                    continue
                    
                results.append({
                    'Source': src_lang,
                    'Target': tgt_lang,
                    'Name': langs,
                    'Link': download_url,
                    'HeadwordCount': '',
                    'Version': '',
                    'Date': ''
                })
                
    print(f"Successfully extracted {len(results)} entries from Wiktionary Dictionaries")
    return results

def normalize_lang2(code):
    """
    Converts 2-letter ISO 639-1 to 3-letter ISO 639-2 using the iso639 module.
    """
    try:
        # Get the language object and return the part2t (terminological) 3-letter code
        code3 = iso639.Lang(code).pt3
        return code3
    except:
        # Return original if conversion fails
        return code

def parse_wikdict():
    url = "https://download.wikdict.com/dictionaries/stardict/"
    results = []
    
    try:
        # Fetching the HTML content
        with urllib.request.urlopen(url) as response:
            html_content = response.read().decode('utf-8')
        # Regex to find the link and the date in the same table row
        # Group 1: full filename, Group 2: src, Group 3: target, Group 4: date
        pattern = re.compile(
            #r'href="(wikdict-(\w{2,3})-(\w{2,3})\.zip)".*?(\d{4}-\d{2}-\d{2})',
            r'href="(wikdict-(\w{2,3})-(\w{2,3})\.zip)".*?(\d{2}\-[A-Za-z]{3}\-\d{4})',
            re.DOTALL
        )
        
        for match in pattern.finditer(html_content):
            filename = match.group(1)
            src_raw = match.group(2)
            tgt_raw = match.group(3)
            date = match.group(4)
            
            # Normalize to 3-letter codes
            src_lang = normalize_lang2(src_raw)
            tgt_lang = normalize_lang2(tgt_raw)
            
            # Name formatting: filename (minus .zip) + ' wiktionary'
            name_base = filename.rsplit('.', 1)[0]
            name = f"{name_base}"
            
            # Build the results dictionary
            results.append({
                'Source': src_lang,
                'Target': tgt_lang,
                'Name': name,
                'Link': url + filename,
                'HeadwordCount': '',
                'Version': '',
                'Date': date
            })
            
    except Exception as e:
        print(f"Error parsing Wikdict: {e}")
        
    print(f"Successfully extracted {len(results)} entries from Wikdict")
    return results

def parse_dict_org():
    url = "https://stardict.uber.space/dict.org/index.html"
    base_url = "https://stardict.uber.space/dict.org/"
    results = []
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html_content = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
        return results
    
    link_pattern = re.compile(r'<a href="(stardict-[^"]+\.tar\.(?:bz2|gz))">([^<]+)</a>')
    word_count_pattern = re.compile(r'(\d+)\s*words')
    
    for match in link_pattern.finditer(html_content):
        filename = match.group(1)
        dict_name = match.group(2)
        
        row_start = match.start()
        row_end = match.end() + 200
        row_context = html_content[row_start:row_end]
        
        wc_match = word_count_pattern.search(row_context)
        headword_count = wc_match.group(1) if wc_match else ''
        
        link = base_url + filename
        
        results.append({
            'Source': 'eng',
            'Target': 'eng',
            'Name': dict_name,
            'Link': link,
            'HeadwordCount': headword_count,
            'Version': '',
            'Date': ''
        })
    
    print(f"Successfully extracted {len(results)} entries from dict.org")
    return results

def parse_freedict_de():
    url = "https://stardict.uber.space/freedict.de/index.html"
    base_url = "https://stardict.uber.space/freedict.de/"
    results = []
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html_content = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
        return results
    
    link_pattern = re.compile(r'<a href="(stardict-freedict-([^"]+)-(\d+\.\d+\.\d+)\.tar\.bz2)">([^<]+)</a>')
    
    for match in link_pattern.finditer(html_content):
        filename = match.group(1)
        src_code = match.group(2)
        version = match.group(3)
        dict_name = match.group(4)
        
        parts = src_code.split('-')
        if len(parts) == 2:
            src_lang = normalize_lang(parts[0])
            tgt_lang = normalize_lang(parts[1])
        else:
            src_lang = ''
            tgt_lang = ''
        
        name = f"{src_code} freedict.de"
        
        link = base_url + filename
        
        results.append({
            'Source': src_lang,
            'Target': tgt_lang,
            'Name': name,
            'Link': link,
            'HeadwordCount': '',
            'Version': version,
            'Date': ''
        })
    
    print(f"Successfully extracted {len(results)} entries from freedict.de")
    return results

def parse_quick():
    url = "https://stardict.uber.space/Quick/index.html"
    base_url = "https://stardict.uber.space/Quick/"
    results = []
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html_content = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
        return results
    
    link_pattern = re.compile(r'<a href="(stardict-quick_([^"]+)-(\d+\.\d+\.\d+)\.tar\.bz2)">([^<]+)</a>')
    
    for match in link_pattern.finditer(html_content):
        filename = match.group(1)
        src_tgt = match.group(2)
        version = match.group(3)
        dict_name = match.group(4)
        
        if 'persian' in src_tgt.lower():
            if src_tgt.startswith('eng-') or dict_name.startswith('quick_eng'):
                src_lang = 'eng'
                tgt_lang = 'per'
            else:
                src_lang = 'per'
                tgt_lang = 'eng'
        else:
            parts = src_tgt.split('-')
            if len(parts) == 2:
                src_lang = normalize_lang(parts[0])
                tgt_lang = normalize_lang(parts[1])
            else:
                src_lang = ''
                tgt_lang = ''
        
        name = f"quick_{src_tgt}"
        
        link = base_url + filename
        
        results.append({
            'Source': src_lang,
            'Target': tgt_lang,
            'Name': name,
            'Link': link,
            'HeadwordCount': '',
            'Version': version,
            'Date': ''
        })
    
    print(f"Successfully extracted {len(results)} entries from Quick")
    return results

def parse_lingvo():
    url = "https://stardict.uber.space/lingvo/index.html"
    base_url = "https://stardict.uber.space/lingvo/"
    results = []
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html_content = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
        return results
    
    full_lang_mapping = {
        'english': 'eng', 'russian': 'rus', 'german': 'deu', 'french': 'fra',
        'chinese': 'zho'
    }
    
    code_2to3 = {
        'en': 'eng', 'ru': 'rus', 'fr': 'fra', 'de': 'deu', 'ge': 'deu', 'it': 'ita',
        'er': 'eng', 're': 'rus', 'gr': 'deu', 'rg': 'rus', 'ir': 'ita', 'ri': 'ita',
        'cr': 'zho'
    }
    
    link_pattern = re.compile(r'<a href="(stardict-[^"]+\.tar\.bz2)">([^<]+)</a>')
    word_count_pattern = re.compile(r'(\d+)\s*words')
    
    for match in link_pattern.finditer(html_content):
        filename = match.group(1)
        dict_name = match.group(2)
        
        row_start = match.start()
        row_end = match.end() + 200
        row_context = html_content[row_start:row_end]
        
        wc_match = word_count_pattern.search(row_context)
        headword_count = wc_match.group(1) if wc_match else ''
        
        src_lang = ''
        tgt_lang = ''
        
        if 'Chinese' in dict_name or 'Chinese-Russian' in dict_name:
            src_lang = 'zho'
            tgt_lang = 'rus'
        elif '(' in dict_name:
            lang_part = dict_name.split('(')[1].split(')')[0]
            if '-' in lang_part:
                parts = lang_part.split('-')
                if len(parts) == 2:
                    src_raw = parts[0].strip().lower()
                    tgt_raw = parts[1].strip().lower()
                    
                    if len(src_raw) == 2:
                        src_lang = code_2to3.get(src_raw, src_raw)
                    elif src_raw in full_lang_mapping:
                        src_lang = full_lang_mapping.get(src_raw, src_raw)
                    
                    if len(tgt_raw) == 2:
                        tgt_lang = code_2to3.get(tgt_raw, tgt_raw)
                    elif tgt_raw in full_lang_mapping:
                        tgt_lang = full_lang_mapping.get(tgt_raw, tgt_raw)
        elif 'Universal' in dict_name:
            if 'English-Russian' in dict_name:
                src_lang = 'eng'
                tgt_lang = 'rus'
            elif 'Russian-English' in dict_name:
                src_lang = 'rus'
                tgt_lang = 'eng'
            elif 'German-Russian' in dict_name:
                src_lang = 'deu'
                tgt_lang = 'rus'
            elif 'Russian-German' in dict_name:
                src_lang = 'rus'
                tgt_lang = 'deu'
            elif 'French-Russian' in dict_name:
                src_lang = 'fra'
                tgt_lang = 'rus'
            elif 'Russian-French' in dict_name:
                src_lang = 'rus'
                tgt_lang = 'fra'
        
        if src_lang and tgt_lang:
            results.append({
                'Source': src_lang,
                'Target': tgt_lang,
                'Name': dict_name,
                'Link': base_url + filename,
                'HeadwordCount': headword_count,
                'Version': '2.4.2',
                'Date': ''
            })
    
    print(f"Successfully extracted {len(results)} entries from Lingvo")
    return results

def parse_babylon_bidirectional():
    url = "https://stardict.uber.space/babylon/bidirectional/index.html"
    base_url = "https://stardict.uber.space/babylon/bidirectional/"
    results = []
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html_content = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
        return results
    
    lang_code_map = {
        'english': 'eng', 'german': 'deu', 'french': 'fra', 'spanish': 'spa',
        'italian': 'ita', 'dutch': 'nld', 'portuguese': 'por', 'hebrew': 'heb',
        'japanese': 'jpn', 'chinese': 'zho', 'chinese_s': 'zho', 'chinese_t': 'zho',
        'russian': 'rus', 'turkish': 'tur', 'swedish': 'swe', 'greek': 'ell',
        'korean': 'kor', 'arabic': 'ara', 'thesaurus': 'eng'
    }
    
    link_pattern = re.compile(r'<a href="(stardict-[^"]+\.tar\.bz2)">([^<]+)</a>')
    
    for match in link_pattern.finditer(html_content):
        filename = match.group(1)
        dict_name = match.group(2).strip()
        
        src_lang = ''
        tgt_lang = ''
        display_name = ''
        
        name_for_parsing = dict_name.replace('-', '_').replace(' ', '_')
        
        if 'English' in dict_name and '_' not in name_for_parsing:
            src_lang = 'eng'
            tgt_lang = 'eng'
            display_name = 'Babylon English'
        elif '_' in name_for_parsing:
            parts = name_for_parsing.split('_')
            src_raw = parts[0].lower()
            tgt_raw = parts[-1].lower()
            
            src_lang = lang_code_map.get(src_raw, src_raw)
            tgt_lang = lang_code_map.get(tgt_raw, tgt_raw)
            
            src_full = parts[0]
            tgt_full = parts[-1].replace('_', ' ')
            display_name = f"Babylon {src_full}-{tgt_full}"
        elif '-' in dict_name:
            parts = dict_name.split('-')
            src_raw = parts[0].strip().lower()
            tgt_raw = parts[1].strip().lower()
            src_lang = lang_code_map.get(src_raw, src_raw)
            tgt_lang = lang_code_map.get(tgt_raw, tgt_raw)
            display_name = f"Babylon {parts[0]}-{parts[1]}"
        
        if src_lang and tgt_lang and display_name:
            results.append({
                'Source': src_lang,
                'Target': tgt_lang,
                'Name': display_name,
                'Link': base_url + filename,
                'HeadwordCount': '',
                'Version': '2.4.2',
                'Date': ''
            })
    
    print(f"Successfully extracted {len(results)} entries from Babylon Bidirectional")
    return results

def main():
    sources_dir = 'sources'
    output_file = 'stardict_dictionaries.tsv'
    all_rows = []
    
    # Rule 3: Keep methods different for every source.
    # We use a mapping of filename to its specific parser function.
    parsers = {
        'freedict-database.json': parse_freedict,
        'dictionaryIndices.md': parse_dictionary_indices,
        'wiktionary': parse_wiktionary,
        'wikdict': parse_wikdict
    }
    if os.path.exists(sources_dir):
        for filename in os.listdir(sources_dir):
            if filename in parsers and filename != 'wiktionary':
                file_path = os.path.join(sources_dir, filename)
                rows = parsers[filename](file_path)
                all_rows.extend(rows)
            elif filename not in parsers:
                print(f"Warning: No parser defined for source '{filename}'")
    else:
        print(f"Error: Directory '{sources_dir}' not found.")
        return
    # Explicitly run wiktionary parser since it doesn't have a local source file
    if 'wiktionary' in parsers:
        rows = parsers['wiktionary'](None)
        all_rows.extend(rows)
                
    # Explicitly run wikdict parser since it doesn't have a local source file
    rows = parse_wikdict()
    all_rows.extend(rows)
    
    # Explicitly run dict.org parser
    rows = parse_dict_org()
    all_rows.extend(rows)
    
    # Explicitly run freedict.de parser
    rows = parse_freedict_de()
    all_rows.extend(rows)
    
    # Explicitly run Quick parser
    rows = parse_quick()
    all_rows.extend(rows)
    
    # Explicitly run Lingvo parser
    rows = parse_lingvo()
    all_rows.extend(rows)
    
    # Explicitly run Babylon Bidirectional parser
    rows = parse_babylon_bidirectional()
    all_rows.extend(rows)
                
    # Rule 1 & 2: Output TSV with mandatory and optional columns
                
    # Rule 1 & 2: Output TSV with mandatory and optional columns
    fieldnames = ['Source', 'Target', 'Name', 'Link', 'HeadwordCount', 'Version', 'Date']
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()
        writer.writerows(all_rows)
        print(f"Successfully generated {output_file} with {len(all_rows)} dictionary entries.")

if __name__ == '__main__':
    main()
