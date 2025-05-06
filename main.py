import xml.etree.ElementTree as ET
import json
from typing import Dict, List, Tuple
import os


# Модельные классы
class Attribute:
    def __init__(self, name: str, type: str):
        self.name = name
        self.type = type

class ClassModel:
    def __init__(self, name: str, is_root: bool, documentation: str):
        self.name = name
        self.is_root = is_root
        self.documentation = documentation
        self.attributes: List[Attribute] = []
        self.child_classes: List[Tuple[str, str, str]] = []  # (child_name, min, max)

class Aggregation:
    def __init__(self, source: str, target: str, source_multiplicity: str, target_multiplicity: str):
        self.source = source
        self.target = target
        self.source_multiplicity = source_multiplicity
        self.target_multiplicity = target_multiplicity

# Парсер модели
class ModelParser:
    @staticmethod
    def parse(xml_content: str) -> Tuple[Dict[str, ClassModel], Dict[str, Aggregation]]:
        root = ET.fromstring(xml_content)
        classes = {}
        aggregations = []
        
        for elem in root:
            if elem.tag == "Class":
                class_name = elem.attrib["name"]
                is_root = elem.attrib.get("isRoot", "false").lower() == "true"
                documentation = elem.attrib.get("documentation", "")
                class_model = ClassModel(class_name, is_root, documentation)
                
                for attr in elem:
                    if attr.tag == "Attribute":
                        class_model.attributes.append(Attribute(attr.attrib["name"], attr.attrib["type"]))
                
                classes[class_name] = class_model
            
            elif elem.tag == "Aggregation":
                aggregations.append(Aggregation(
                    elem.attrib["source"],
                    elem.attrib["target"],
                    elem.attrib["sourceMultiplicity"],
                    elem.attrib["targetMultiplicity"]
                ))
        
        # Обрабатываем агрегации для заполнения child_classes
        for agg in aggregations:
            target_class = classes.get(agg.target)
            if target_class:
                target_class.child_classes.append((
                    agg.source,
                    agg.source_multiplicity.split("..")[0],
                    agg.source_multiplicity.split("..")[-1] if ".." in agg.source_multiplicity else agg.source_multiplicity
                ))
        

        return classes, aggregations

# Генераторы выходных файлов
class ConfigXmlGenerator:
    @staticmethod
    def generate(model: Dict[str, ClassModel]) -> str:
        root_class = next((c for c in model.values() if c.is_root), None)
        if not root_class:
            raise ValueError("No root class found in the model")
        
        def build_xml(class_name: str) -> ET.Element:
            class_model = model[class_name]
            element = ET.Element(class_name)

            for attr in class_model.attributes:
                attr_elem = ET.SubElement(element, attr.name)
                attr_elem.text = attr.type
            
            for child_name, _, _ in class_model.child_classes:
                child_elem = build_xml(child_name)
                element.append(child_elem)

            return element
        
        root_elem = build_xml(root_class.name)
        ET.indent(root_elem)
        return ET.tostring(root_elem, encoding="unicode")

class MetaJsonGenerator:
    @staticmethod
    def generate(model: Dict[str, ClassModel]) -> str:
        result = []
        
        for class_name, class_model in model.items():

            parameters = []
            
            # Добавляем атрибуты
            for attr in class_model.attributes:
                parameters.append({
                    "name": attr.name,
                    "type": attr.type
                })
            
            # Добавляем дочерние классы
            for child_name, min_val, max_val in class_model.child_classes:
                parameters.append({
                    "name": child_name,
                    "type": "class"
                })
            
            # Формируем запись для класса
            class_entry = {
                "class": class_name,
                "documentation": class_model.documentation,
                "isRoot": class_model.is_root,
                "parameters": parameters
            }
            
            # Добавляем min/max для дочерних классов (если они есть)
            if class_model.child_classes:
                _, min_val, max_val = class_model.child_classes[0]
                class_entry["min"] = min_val
                class_entry["max"] = max_val
            
            result.append(class_entry)
        
        return json.dumps(result, indent=4)

class ConfigComparator:
    @staticmethod
    def compare(config: Dict, patched_config: Dict) -> Dict:
        additions = []
        deletions = []
        updates = []
        
        # Все ключи из обоих конфигов
        all_keys = set(config.keys()).union(set(patched_config.keys()))
        
        for key in all_keys:
            if key in patched_config and key not in config:
                # Добавленный параметр
                additions.append({
                    "key": key,
                    "value": patched_config[key]
                })
            elif key in config and key not in patched_config:
                # Удаленный параметр
                deletions.append(key)
            elif config[key] != patched_config[key]:
                # Измененный параметр
                updates.append({
                    "key": key,
                    "from": config[key],
                    "to": patched_config[key]
                })
        
        return {
            "additions": additions,
            "deletions": deletions,
            "updates": updates
        }
    
    @staticmethod
    def apply_delta(config: Dict, delta: Dict) -> Dict:
        result = config.copy()
        
        # Применяем удаления
        for key in delta["deletions"]:
            if key in result:
                del result[key]
        
        # Применяем обновления
        for update in delta["updates"]:
            result[update["key"]] = update["to"]
        
        # Применяем добавления
        for addition in delta["additions"]:
            result[addition["key"]] = addition["value"]
        
        return result


def main():
    # Создаем папку out, если ее нет
    os.makedirs("out", exist_ok=True)
    
    # Читаем входные файлы
    with open("input/impulse_test_input.xml", "r", encoding="utf-8") as f:
        xml_content = f.read()
    
    with open("input/config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    
    with open("input/patched_config.json", "r", encoding="utf-8") as f:
        patched_config = json.load(f)
    
    # Парсим модель
    model, _ = ModelParser.parse(xml_content)
    
    # Генерируем config.xml
    config_xml = ConfigXmlGenerator.generate(model)
    with open("out/config.xml", "w", encoding="utf-8") as f:
        f.write(config_xml)
    
    # Генерируем meta.json
    meta_json = MetaJsonGenerator.generate(model)
    with open("out/meta.json", "w", encoding="utf-8") as f:
        f.write(meta_json)
    
    # Сравниваем конфиги и генерируем delta.json
    delta = ConfigComparator.compare(config, patched_config)
    with open("out/delta.json", "w", encoding="utf-8") as f:
        json.dump(delta, f, indent=4)
    
    # Применяем дельту и генерируем res_patched_config.json
    res_patched_config = ConfigComparator.apply_delta(config, delta)
    with open("out/res_patched_config.json", "w", encoding="utf-8") as f:
        json.dump(res_patched_config, f, indent=4)

if __name__ == "__main__":
    main()