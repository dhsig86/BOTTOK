import os
import re
import unicodedata

dir_path = r'c:\Users\drdhs\OneDrive\Documentos\MEDICAL GPT\books\biblioteca'

def normalize_name(name):
    # Separa extensao
    name_no_ext, ext = os.path.splitext(name)
    
    # Remove acentos
    name_no_ext = unicodedata.normalize('NFKD', name_no_ext).encode('ASCII', 'ignore').decode('utf-8')
    
    # Substitui qualquer coisa que não seja letra, número ou hífen por underscore (_)
    name_no_ext = re.sub(r'[^a-zA-Z0-9\-]', '_', name_no_ext)
    
    # Remove underscores duplicados
    name_no_ext = re.sub(r'_+', '_', name_no_ext)
    
    # Remove underscores nas pontas
    name_no_ext = name_no_ext.strip('_')
    
    # Adiciona a extensão de volta e converte para minúsculo
    return name_no_ext.lower() + ext.lower()

arquivos_renomeados = 0

for f in os.listdir(dir_path):
    if os.path.isfile(os.path.join(dir_path, f)):
        old_path = os.path.join(dir_path, f)
        new_name = normalize_name(f)
        new_path = os.path.join(dir_path, new_name)
        
        if old_path != new_path:
            # Tratamento de colisão (se 2 arquivos ficarem com o mesmo nome exato)
            count = 1
            temp_path = new_path
            
            # Necessário prever se é só a diferença de capitalização (windows ignora case no exists)
            # Mas vamos renomear de qualquer forma mudando o path final
            while os.path.exists(temp_path) and temp_path.lower() != old_path.lower():
                name_no_ext, ext = os.path.splitext(new_name)
                temp_path = os.path.join(dir_path, f"{name_no_ext}_{count}{ext}")
                count += 1
                
            os.rename(old_path, temp_path)
            print(f"Renomeado: '{f}' -> '{os.path.basename(temp_path)}'")
            arquivos_renomeados += 1

print(f"\nTotal de arquivos renomeados: {arquivos_renomeados}")
