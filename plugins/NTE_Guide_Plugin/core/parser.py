"""
异环攻略插件 - HTML 解析模块
"""
import re
import json
from typing import Optional

from bs4 import BeautifulSoup

from graci import get_logger

from .fetcher import fetch_url, fetch_image
from ..config import ATTR_MAP, RARITY_MAP, SLUG_NAME_MAP, BASE_URL

logger = get_logger("NTEGuide.parser")

# ── 工具 ──

def _clean(text: str) -> str:
    """清理多余空白"""
    return re.sub(r'\s+', ' ', text).strip()


def _chinese_attr(raw: str) -> str:
    """将属性名转为中文"""
    key = raw.strip().lower()
    return ATTR_MAP.get(key, key)


def _chinese_rarity(raw: str) -> str:
    """将稀有度转为中文"""
    key = raw.strip()
    mapped = RARITY_MAP.get(key, key)
    return mapped


def _extract_skills_from_rsc(html: str) -> dict:
    """从 RSC (React Server Components) payload 提取技能描述"""
    try:
        # RSC payload 中 \" 实际上是 JSON 的 "（被 JS 字符串转义了）
        # 先全局替换 \" 为 " 恢复 JSON
        clean = html.replace('\\"', '"')
        
        start_marker = '"skills":{'
        start_idx = clean.find(start_marker)
        if start_idx < 0:
            return {}
        
        end_marker = '"locale":"zh"'
        end_idx = clean.find(end_marker, start_idx)
        if end_idx < 0:
            return {}
        
        # 提取 skills 值 JSON
        brace_start = clean.find('{', start_idx + len(start_marker) - 1)
        if brace_start < 0:
            return {}
        
        # 在 end_idx 前找匹配的 }
        search_end = end_idx
        depth = 1
        pos = brace_start + 1
        in_str = False
        
        while pos < search_end and depth > 0:
            ch = clean[pos]
            if ch == '\\' and in_str:
                pos += 2  # 跳过 JSON 转义序列（如 \\n, \", \\\\ 等）
                continue
            if ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
            pos += 1
        
        if depth != 0:
            return {}
        
        json_str = clean[brace_start:pos]
        # 现在 JSON 中的 \" 已经是 "，但 JSON 转义还在（\\n 等）
        # 需要还原 JSON 转义
        json_str = json_str.replace('\\n', '\n').replace('\\\\', '\\')

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    except Exception as e:
        logger.debug(f"RSC技能提取失败: {e}")

    return {}


# ── 角色 ──

async def get_character_list() -> list:
    """获取全角色列表 [{name, slug, img_url}]"""
    html = await fetch_url(f"{BASE_URL}/characters/", cache_type="character_list")
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    results = []
    seen = set()

    for a in soup.find_all('a', href=re.compile(r'/zh/characters/\w+/\w*$')):
        href = a.get('href', '')
        # 排除 /zh/characters/ 根路径
        if href.count('/') < 4:
            continue
        slug = href.rstrip('/').split('/')[-1]
        if not slug or slug in seen:
            continue

        # 从 img alt 中提取中文名（如 "薄荷 - character in ..."）
        img_tag = a.find('img')
        name = ""
        img_url = ""
        if img_tag:
            alt_text = img_tag.get('alt', '')
            # 取 " - " 前面的中文名
            if ' - ' in alt_text:
                name = alt_text.split(' - ')[0].strip()
            if img_tag.get('src'):
                src = img_tag['src']
                img_url = src if src.startswith('http') else f"https://nteguide.com{src}"
                img_url = img_url.split('?')[0]

        if not name:
            continue
        seen.add(slug)
        results.append({"name": name, "slug": slug, "img_url": img_url})

    return results


async def get_character_detail(slug: str) -> Optional[dict]:
    """获取角色详情"""
    html = await fetch_url(f"{BASE_URL}/characters/{slug}/", cache_type="character_detail")
    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    data = {"slug": slug}

    # 1. 标题 / 名称
    title_tag = soup.find('title')
    data["title"] = _clean(title_tag.get_text()) if title_tag else slug

    # 2. 角色概览表
    table = soup.find('table')
    if table:
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 2:
                key = _clean(cells[0].get_text())
                val = _clean(cells[1].get_text())
                if key == "名称":
                    data["name"] = val.split("(")[0].strip()
                elif key == "定位":
                    data["role"] = val
                elif key == "属性":
                    data["attr"] = _chinese_attr(val)
                elif key == "稀有度":
                    data["rarity"] = _chinese_rarity(val)
                elif key == "武器类型":
                    data["weapon_type"] = val
                elif key == "阵营":
                    data["faction"] = val
                elif key == "中文配音":
                    data["cn_va"] = val
                elif key == "日文配音":
                    data["jp_va"] = val
                elif key == "定位/稀有度":
                    parts = val.split("·")
                    if len(parts) == 2:
                        data["role"] = _clean(parts[0])
                        data["rarity"] = _chinese_rarity(_clean(parts[1]))

    if "name" not in data:
        data["name"] = slug

    # 3. 角色图片
    img_tags = soup.find_all('img')
    for img in img_tags:
        src = img.get('src', '')
        alt = img.get('alt', '')
        if slug.replace('-', '').lower() in src.lower().replace('-', '').replace('_', ''):
            img_url = src if src.startswith('http') else f"https://nteguide.com{src}"
            img_url = img_url.split('?')[0]  # 去掉 v=7 参数
            data["img_url"] = img_url
            break
    if "img_url" not in data:
        # 兜底
        for img in img_tags:
            src = img.get('src', '')
            if '/images/characters/' in src:
                img_url = src if src.startswith('http') else f"https://nteguide.com{src}"
                img_url = img_url.split('?')[0]
                data["img_url"] = img_url
                break

    # 4. 评级信息（从标题提取）
    title_text = data.get("title", "")
    m = re.search(r'\((.+?)\)', title_text)
    if m:
        data["tier"] = m.group(1)

    # 4.5 角色介绍和评级描述
    full_text = soup.get_text()
    # 评级描述（全文正则搜索）
    m_rating = re.search(r'强度评级[：:]\s*(.*?)(?:最佳武器|最佳弧盘|最佳配队|\n|$)', full_text)
    if m_rating:
        data["rating_desc"] = _clean(m_rating.group(1))
    # 角色定位
    m_role = re.search(r'角色定位[：:]\s*(.*?)(?:强度评级|\n|$)', full_text)
    if m_role:
        data["role_detail"] = _clean(m_role.group(1))
    # 角色介绍（找含"是异环中的"的p标签）
    for p in soup.find_all('p'):
        ptxt = p.get_text(strip=True)
        if '是异环中的' in ptxt:
            data["introduction"] = ptxt[:200]
            break

    # 5. 技能（含描述）
    skills = []
    # 找技能区大容器
    skill_container = None
    for div in soup.find_all('div', class_=lambda c: c and 'space-y-2' in str(c) if c else False):
        txt = div.get_text()
        if '普攻' in txt and ('战技' in txt or '终结技' in txt):
            skill_container = div
            break

    if skill_container:
        skill_text = skill_container.get_text('\n', strip=True)
        lines = [l for l in skill_text.split('\n') if l.strip() and l.strip() not in ('⚔', '✦', '★', '◆', '倍率')]
        current_type = None
        for line in lines:
            # 遇到被动天赋停止技能解析
            if line in ("被动天赋",) or line.startswith("被动"):
                break
            if line in ("普攻", "战技", "终结技"):
                current_type = line
                skills.append({"type": line, "name": "", "desc": ""})
            elif current_type:
                entry = skills[-1]
                # 跳过技能等级数字和纯数字行
                if re.match(r'^\d+段|^\d+级|^\d+%|^Lv\.|^\d+$', line):
                    continue
                if not entry["name"]:
                    entry["name"] = line
                elif not entry["desc"] and len(line) > 6 and any(c.isalpha() for c in line):
                    # 只取第一条长文本作为描述，忽略倍率数据行
                    if not any(kw in line for kw in ["ATK", "%", ":", "×"]):
                        entry["desc"] = line
    else:
        # 兜底：原逻辑
        for label in ["普攻", "战技", "终结技"]:
            span = soup.find('span', string=re.compile(label))
            if span:
                parent = span.find_parent(['div', 'section'])
                if parent:
                    p_tag = parent.find('p', class_=re.compile('text-sm'))
                    skill_name = _clean(p_tag.get_text()) if p_tag else ""
                    skills.append({"type": label, "name": skill_name, "desc": ""})
    data["skills"] = skills

    # 从 RSC payload 提取完整技能描述（含战技/终结技折叠描述）
    rsc_skills = _extract_skills_from_rsc(html)
    if rsc_skills:
        type_map = {"normalAttack": "普攻", "skill": "战技", "ultimate": "终结技"}
        for entry in data["skills"]:
            rsc_key = None
            for k, v in type_map.items():
                if v == entry["type"]:
                    rsc_key = k
                    break
            if rsc_key and rsc_key in rsc_skills:
                desc = rsc_skills[rsc_key].get("description", "")
                if desc and desc != "...":
                    entry["desc"] = desc

    # 6. 被动天赋
    passives = []
    for h3 in soup.find_all('h3'):
        if '被动' in h3.get_text():
            parent = h3.find_parent(['div', 'section'])
            if parent:
                buttons = parent.find_all('button')
                for btn in buttons:
                    p_name = _clean(btn.get_text())
                    # 清洗 ◆ 和 "被动 X" 前缀
                    p_name = re.sub(r'^◆+\s*', '', p_name)
                    p_name = re.sub(r'^被动\s*\d+\s*', '', p_name)
                    p_name = p_name.strip()
                    if p_name:
                        passives.append(p_name)
    data["passives"] = passives

    # 7. 配装推荐（结构化）
    gear = {
        "best_weapon": "",
        "disk_set": "",
        "main_stats": "",
        "sub_stats": "",
    }
    for h2 in soup.find_all('h2'):
        if '配装' in h2.get_text():
            section = h2.find_parent('section')
            if section:
                div = section.find('div', class_=lambda c: c and 'rounded-xl' in str(c) if c else False)
                if div:
                    for child in div.children:
                        if hasattr(child, 'name') and child.name:
                            h3_t = child.find('h3')
                            if not h3_t:
                                continue
                            title = _clean(h3_t.get_text())
                            content = _clean(child.get_text().replace(h3_t.get_text(), ''))
                            if '最佳武器' in title:
                                gear["best_weapon"] = content
                            elif '磁盘套装' in title:
                                gear["disk_set"] = content
                            elif '主词条' in title:
                                gear["main_stats"] = content
                            elif '副词条' in title:
                                gear["sub_stats"] = content
                # 也保存原始文本兜底
                text = section.get_text('\n')
                lines = [l for l in text.split('\n') if l.strip()]
                gear["_raw"] = '\n'.join(lines)
            break
    data["gear"] = gear

    # 8. 升级材料（跳过空数据段）
    materials = []
    for h3_text in ["等级 1-10", "等级 11-20", "等级 21-30", "等级 31-40", "等级 41-50", "等级 51-60"]:
        h3 = soup.find('h3', string=re.compile(re.escape(h3_text)))
        if h3:
            parent = h3.find_parent(['div', 'section'])
            if parent:
                mt = _clean(parent.get_text())
                mt = mt.replace(h3_text, '').strip()
                # 跳过空数据（如只有 x4 没有材料名）
                if mt and not mt in ('x', 'x1', 'x2', 'x3', 'x4', 'x5'):
                    materials.append({"level": h3_text, "materials": mt})
    data["materials"] = materials

    # 9. 升级计算器概览（角色→材料映射表）
    calc_table = soup.find('table')
    if calc_table:
        for row in calc_table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 2 and _clean(cells[0].get_text()) == data.get("name"):
                data["level_materials_summary"] = _clean(cells[1].get_text())

    # 10. 推荐配队（3个子元素一组：h3队伍名 → div成员 → p描述）
    teams = []
    for h2 in soup.find_all('h2'):
        if '配队' in h2.get_text():
            section = h2.find_parent('section')
            if section:
                div = section.find('div', class_=lambda c: c and 'rounded-xl' in str(c) if c else False)
                if div:
                    children = [ch for ch in div.children if hasattr(ch, 'name') and ch.name]
                    # 每次取3个一组: h3(队名) + div(成员) + p(描述)
                    for i in range(0, len(children) - 2, 3):
                        name_el = children[i]
                        members_el = children[i+1]
                        desc_el = children[i+2]

                        team_name = _clean(name_el.get_text())
                        member_slugs = _clean(members_el.get_text(separator=' ', strip=True)).split()
                        member_names = [SLUG_NAME_MAP.get(s, s) for s in member_slugs if s]
                        desc = _clean(desc_el.get_text())

                        if team_name and member_names:
                            teams.append({
                                "name": team_name,
                                "members": member_names,
                                "desc": desc or "推荐配队方案",
                            })
            break
    data["teams"] = teams

    return data


# ── 武器 ──

async def get_weapon_list() -> list:
    """获取全武器列表 [{name, slug, img_url}]"""
    html = await fetch_url(f"{BASE_URL}/weapons/", cache_type="weapon_list")
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    results = []
    seen = set()

    for a in soup.find_all('a', href=re.compile(r'/zh/weapons/\w+[\w-]*/$')):
        href = a.get('href', '')
        if href.count('/') < 4:
            continue
        slug = href.rstrip('/').split('/')[-1]
        if not slug or slug in seen:
            continue

        img_tag = a.find('img')
        name = ""
        img_url = ""
        if img_tag:
            alt_text = img_tag.get('alt', '')
            if ' - ' in alt_text:
                name = alt_text.split(' - ')[0].strip()
            if img_tag.get('src'):
                src = img_tag['src']
                img_url = src if src.startswith('http') else f"https://nteguide.com{src}"
                img_url = img_url.split('?')[0]

        if not name:
            continue
        seen.add(slug)
        results.append({"name": name, "slug": slug, "img_url": img_url})

    return results


async def get_weapon_detail(slug: str) -> Optional[dict]:
    """获取武器/弧盘详情"""
    html = await fetch_url(f"{BASE_URL}/weapons/{slug}/", cache_type="weapon_detail")
    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    data = {"slug": slug}

    title_tag = soup.find('title')
    data["title"] = _clean(title_tag.get_text()) if title_tag else slug

    # 获取名称
    h1 = soup.find('h1')
    if h1:
        data["name"] = _clean(h1.get_text())

    # 获取图片
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if slug.replace('-', '') in src.lower().replace('-', '').replace('_', ''):
            img_url = src if src.startswith('http') else f"https://nteguide.com{src}"
            data["img_url"] = img_url.split('?')[0]
            break

    # 从概览表提取结构化数据
    table = soup.find('table')
    if table:
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                key = _clean(cells[0].get_text())
                val = _clean(cells[1].get_text())
                if '稀有度' in key:
                    data["rarity"] = val
                elif '类型' in key:
                    data["type"] = val
                elif key == "ATK":
                    data["atk"] = val
                elif '攻击力' in key or '副属性' in key:
                    data["sub_stat"] = val
                elif '获取方式' in key:
                    data["acquisition"] = val
                elif '适配角色' in key:
                    data["compatible_chars"] = val

    # 弧盘效果
    for h2 in soup.find_all('h2'):
        if '效果' in h2.get_text():
            section = h2.find_parent('section')
            if section:
                effect_text = section.get_text('\n', strip=True)
                # 去掉标题，提取效果名称和描述
                effect_lines = [l for l in effect_text.split('\n') if l.strip()]
                if len(effect_lines) >= 2:
                    data["effect_name"] = effect_lines[1]  # 第二行通常是效果名
                    if len(effect_lines) >= 3:
                        data["effect_desc"] = effect_lines[2]  # 第三行是描述
                else:
                    data["effect_name"] = effect_lines[0] if effect_lines else ""
            break

    # 适配角色列表（从适配角色 section 提取中文名）
    compatible_names = []
    for h2 in soup.find_all('h2'):
        if '适配' in h2.get_text():
            section = h2.find_parent('section')
            if section:
                for h3 in section.find_all('h3'):
                    txt = _clean(h3.get_text())
                    if txt and len(txt) < 10:
                        compatible_names.append(txt)
            break
    if compatible_names:
        data["compatible_chars_list"] = compatible_names

    return data


# ── 材料 ──

async def get_material_list() -> list:
    """获取材料列表 [{name, slug, category, stars}]"""
    html = await fetch_url(f"{BASE_URL}/materials/", cache_type="material_list")
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    results = []

    for a in soup.find_all('a', href=re.compile(r'/zh/materials/\w+')):
        href = a.get('href', '')
        slug = href.split('/')[-1]
        if not slug or slug == 'materials':
            continue

        name = _clean(a.get_text())
        if not name:
            continue

        # 星数和分类（从父级文本提取）
        parent = a.find_parent(['div', 'li'])
        category = ""
        stars = ""
        if parent:
            p_text = parent.get_text()
            m = re.search(r'[★★★☆☆]{1,5}', p_text)
            if m:
                stars = m.group()
            m2 = re.search(r'\[(\w+)\]', p_text)
            if m2:
                category = m2.group(1)

        results.append({"name": name, "slug": slug, "category": category, "stars": stars})

    return results


# ── 兑换码 ──

async def get_redeem_codes() -> list:
    """获取兑换码列表 [{code, desc}]"""
    html = await fetch_url(f"{BASE_URL}/redeem-codes/", cache_type="redeem_codes")
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    results = []

    text = soup.get_text()
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # 找兑换码模式（全大写字母+数字）
    for line in lines:
        codes = re.findall(r'\b[A-Z0-9]{6,20}\b', line)
        for code in codes:
            if code not in [c["code"] for c in results]:
                results.append({"code": code, "desc": line[:60]})

    return results


# ── 升级计算器 ──

async def get_leveling_materials(slug: str) -> Optional[list]:
    """获取角色升级所需材料"""
    detail = await get_character_detail(slug)
    if not detail:
        return None
    return detail.get("materials", [])


# ── 搜索 ──

async def search(query: str) -> dict:
    """跨分类搜索"""
    query = query.lower().strip()
    result = {"characters": [], "weapons": [], "materials": []}

    # 搜索角色
    chars = await get_character_list()
    for c in chars:
        if query in c["name"].lower():
            result["characters"].append(c)

    # 搜索武器
    weaps = await get_weapon_list()
    for w in weaps:
        if query in w["name"].lower():
            result["weapons"].append(w)

    # 搜索材料
    mats = await get_material_list()
    for m in mats:
        if query in m["name"].lower():
            result["materials"].append(m)

    return result
