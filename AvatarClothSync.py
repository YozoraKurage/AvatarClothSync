#Github Copilot Claude3.5に感謝を...

bl_info = {
    "name": "AvatarClothSync",
    "author": "YozoraKurage",
    "version": (0, 0, 1),
    "blender": (3, 6, 0),
    "category": "Object",
    "description": "非破壊で衣装フィッティングを行うツール"
}

import bpy
from bpy.props import PointerProperty, BoolProperty, StringProperty, CollectionProperty, IntProperty
from bpy.types import Panel, Operator, PropertyGroup
import re

# Unity Humanoid規格のボーン名リスト
HUMANOID_BONES = {
    'hips': ['hips', 'hip', 'pelvis'],
    'spine': ['spine'],
    'chest': ['chest', 'spine1'],
    'upperChest': ['upper_chest', 'spine2', 'spine3'],
    'neck': ['neck'],
    'head': ['head'],
    'leftShoulder': ['left_shoulder', 'l_shoulder', 'shoulder_l', 'shoulder.l'],
    'leftUpperArm': ['left_upper_arm', 'l_arm', 'upperarm_l', 'upper_arm.l'],
    'leftLowerArm': ['left_lower_arm', 'l_forearm', 'lowerarm_l', 'forearm.l'],
    'leftHand': ['left_hand', 'l_hand', 'hand_l', 'hand.l'],
    'rightShoulder': ['right_shoulder', 'r_shoulder', 'shoulder_r', 'shoulder.r'],
    'rightUpperArm': ['right_upper_arm', 'r_arm', 'upperarm_r', 'upper_arm.r'],
    'rightLowerArm': ['right_lower_arm', 'r_forearm', 'lowerarm_r', 'forearm.r'],
    'rightHand': ['right_hand', 'r_hand', 'hand_r', 'hand.r'],
    'leftUpperLeg': ['left_upper_leg', 'l_thigh', 'thigh_l', 'thigh.l'],
    'leftLowerLeg': ['left_lower_leg', 'l_shin', 'shin_l', 'shin.l'],
    'leftFoot': ['left_foot', 'l_foot', 'foot_l', 'foot.l'],
    'rightUpperLeg': ['right_upper_leg', 'r_thigh', 'thigh_r', 'thigh.r'],
    'rightLowerLeg': ['right_lower_leg', 'r_shin', 'shin_r', 'shin.r'],
    'rightFoot': ['right_foot', 'r_foot', 'foot_r', 'foot.r']
}

class ClothingFitProperties(PropertyGroup):
    avatar_armature: PointerProperty(
        name="アバターのアーマチュア",
        type=bpy.types.Object,
        description="基準となるアバターのアーマチュア"
    )
    cloth_armature: PointerProperty(
        name="衣装のアーマチュア",
        type=bpy.types.Object,
        description="フィッティングする衣装のアーマチュア"
    )
    is_synced: BoolProperty(
        name="同期中",
        default=False
    )

class BonePairItem(PropertyGroup):
    avatar_bone: StringProperty(name="アバターボーン")
    cloth_bone: StringProperty(name="衣装ボーン")

class ArmaturePairMapping(PropertyGroup):
    avatar_armature: StringProperty(name="アバターアーマチュア")
    cloth_armature: StringProperty(name="衣装アーマチュア")
    bone_pairs: CollectionProperty(type=BonePairItem)

# 未マッチボーン選択ダイアログ
class OBJECT_OT_show_unmatched_bones(Operator):
    bl_idname = "object.show_unmatched_bones"
    bl_label = "未マッチングボーン"
    bl_description = "マッチングできなかったHumanoidボーンを表示"
    
    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        for bone in context.scene.unmatched_bones.split(','):
            if bone:
                layout.label(text=bone)

def find_matching_bone(bone_name, armature):
    # 完全一致を試す
    if bone_name in armature.pose.bones:
        return bone_name
    
    bone_name_lower = bone_name.lower()
    
    # 正規化関数
    def normalize_bone_name(name):
        return re.sub(r'[._\-\s]', '', name.lower())
    
    normalized_bone = normalize_bone_name(bone_name)
    
    # 正規化した名前で比較
    for bone in armature.pose.bones:
        if normalize_bone_name(bone.name) == normalized_bone:
            return bone.name
    
    # Humanoidボーン名での検索
    for humanoid_bone, variations in HUMANOID_BONES.items():
        if any(variation in bone_name_lower for variation in variations):
            for target_bone in armature.pose.bones:
                target_lower = target_bone.name.lower()
                if any(normalize_bone_name(variation) in normalize_bone_name(target_lower) for variation in variations):
                    return target_bone.name
    
    return None

class OBJECT_OT_sync_armatures(Operator):
    bl_idname = "object.sync_armatures"
    bl_label = "アーマチュア同期"
    bl_description = "選択された2つのアーマチュアを同期します"
    bl_options = {'REGISTER', 'UNDO'}
    
    def find_matching_bone(self, bone_name, armature):
        return find_matching_bone(bone_name, armature)
    
    def execute(self, context):
        props = context.scene.clothing_fit_props
        if not props.avatar_armature or not props.cloth_armature:
            self.report({'ERROR'}, "アーマチュアを両方選択してください")
            return {'CANCELLED'}
            
        unmatched_bones = []
        
        if not props.is_synced:
            # ボーンの制約を追加
            for cloth_bone in props.cloth_armature.pose.bones:
                avatar_bone_name = self.find_matching_bone(cloth_bone.name, props.avatar_armature)
                if avatar_bone_name:
                    avatar_bone = props.avatar_armature.pose.bones[avatar_bone_name]
                    const = avatar_bone.constraints.new('COPY_TRANSFORMS')
                    const.target = props.cloth_armature
                    const.subtarget = cloth_bone.name
                else:
                    # Humanoidボーンの場合のみエラーリストに追加
                    bone_is_humanoid = False
                    for variations in HUMANOID_BONES.values():
                        if any(variation in cloth_bone.name.lower() for variation in variations):
                            bone_is_humanoid = True
                            break
                    if bone_is_humanoid:
                        unmatched_bones.append(cloth_bone.name)
            
            # 未マッチングボーンがある場合はダイアログを表示
            if unmatched_bones:
                context.scene.unmatched_bones = ','.join(unmatched_bones)
                bpy.ops.object.show_unmatched_bones('INVOKE_DEFAULT')
                
            props.is_synced = True
        else:
            # 制約を解除
            for bone in props.avatar_armature.pose.bones:
                for const in bone.constraints:
                    bone.constraints.remove(const)
            props.is_synced = False
            
        return {'FINISHED'}

class VIEW3D_PT_clothing_fit(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "衣装フィット"
    bl_label = "衣装フィッティング"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.clothing_fit_props
        
        layout.prop(props, "avatar_armature")
        layout.prop(props, "cloth_armature")
        
        # 同期状態をより視覚的に表示
        row = layout.row()
        row.alert = props.is_synced  # 同期中は赤く表示
        if props.is_synced:
            row.operator("object.sync_armatures", text="同期中 - クリックで解除", icon='LINKED')
        else:
            row.operator("object.sync_armatures", text="同期開始", icon='UNLINKED')

classes = (
    ClothingFitProperties,
    BonePairItem,
    ArmaturePairMapping,
    OBJECT_OT_show_unmatched_bones,
    OBJECT_OT_sync_armatures,
    VIEW3D_PT_clothing_fit
)

def register():
    bpy.types.Scene.unmatched_bones = bpy.props.StringProperty(default="")
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.clothing_fit_props = PointerProperty(type=ClothingFitProperties)
    bpy.types.Scene.armature_mappings = CollectionProperty(type=ArmaturePairMapping)

def unregister():
    del bpy.types.Scene.clothing_fit_props
    del bpy.types.Scene.unmatched_bones
    del bpy.types.Scene.armature_mappings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()