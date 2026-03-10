import json
import csv
import os
import urllib.request
import re

def parse_freedict(file_path):
    """
    Parses the freedict-database.json file and extracts StarDict links.
    """
    results = []
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
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
        'sanskrit': 'sa', 'hindi': 'hi', 'marathi': 'mr', 'gujarati': 'gu',
        'nepali': 'ne', 'panjabi': 'pa', 'oriya': 'or', 'assamese': 'as',
        'bengali': 'bn', 'kannada': 'kn', 'tamil': 'ta', 'malayalam': 'ml',
        'sinhala': 'si', 'telugu': 'te', 'urdu': 'ur', 'kashmiri': 'ks',
        'tibetan': 'bo', 'english': 'en', 'pali': 'pi', 'prakrit': 'pra',
        'ayurveda': 'sa', 'divehi': 'dv'
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
            # Check for direct matches first
            if repo_name in repo_to_code.values():
                default_lang = repo_name
            else:
                for key, code in repo_to_code.items():
                    if key in repo_name:
                        default_lang = code
                        break
        
        if not src_lang:
            src_lang = default_lang
        if not tgt_lang:
            tgt_lang = default_lang
                
        # Parse Name and Date from filename
        # Expected pattern: name__date_time__size.tar.gz
        name = ''
        date = ''
        if '__' in filename:
            file_parts = filename.split('__')
            name = file_parts[0]
            date_str = file_parts[1]
            date = date_str[:10] if len(date_str) >= 10 else date_str
        else:
            name = filename.replace('.tar.gz', '')
        
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
    Parses the dictionaryIndices.md file and processes each tars.MD URL.
    """
    results = []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Extract all http/https links pointing to tars.MD or tars_external.MD
    # The links are enclosed in < > brackets
    url_pattern = re.compile(r'<(https://raw\.githubusercontent\.com/indic-dict/[^>]*tars.*\.MD)>')
    urls = url_pattern.findall(content)
    
    for url in urls:
        print(f"Fetching from {url}")
        rows = parse_tars_md(url)
        results.extend(rows)
        
    print(f"Total entries from dictionaryIndices.md: {len(results)}")
    return results

def main():
    sources_dir = 'sources'
    output_file = 'stardict_dictionaries.tsv'
    all_rows = []
    
    # Rule 3: Keep methods different for every source.
    # We use a mapping of filename to its specific parser function.
    parsers = {
        'freedict-database.json': parse_freedict,
        'dictionaryIndices.md': parse_dictionary_indices
        # Future sources can be added here with their respective parser functions
    }
    
    if os.path.exists(sources_dir):
        for filename in os.listdir(sources_dir):
            if filename in parsers:
                file_path = os.path.join(sources_dir, filename)
                rows = parsers[filename](file_path)
                all_rows.extend(rows)
            else:
                print(f"Warning: No parser defined for source '{filename}'")
    else:
        print(f"Error: Directory '{sources_dir}' not found.")
        return
                
    # Rule 1 & 2: Output TSV with mandatory and optional columns
    fieldnames = ['Source', 'Target', 'Name', 'Link', 'HeadwordCount', 'Version', 'Date']
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()
        writer.writerows(all_rows)
        print(f"Successfully generated {output_file} with {len(all_rows)} dictionary entries.")

if __name__ == '__main__':
    main()
