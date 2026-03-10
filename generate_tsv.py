import json
import csv
import os

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

def main():
    sources_dir = 'sources'
    output_file = 'stardict_dictionaries.tsv'
    all_rows = []
    
    # Rule 3: Keep methods different for every source.
    # We use a mapping of filename to its specific parser function.
    parsers = {
        'freedict-database.json': parse_freedict
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
