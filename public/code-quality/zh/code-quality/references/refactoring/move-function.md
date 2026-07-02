# Move Function

## 它是什么

Move Function 会把一个函数（或方法）从一个模块或 class 迁移到一个更适合拥有它的地方。程序的结构反映的是行为住在哪里；随着理解变深，行为往往会发现自己其实放错了位置。Move Function 就是用来修正这一点的 - 让代码靠近它所使用的数据，以及它一起改变的其他代码。

```python
# before: account.py reaches into a rate table it doesn't own
class Account:
    def overdraft_charge(self):
        if self.type.is_premium:
            base = 10
            return base + max(0, self.days_overdrawn - 7) * 0.85
        return self.days_overdrawn * 1.75

# after: the charge rule lives with the account type that defines it
class AccountType:
    def overdraft_charge(self, days_overdrawn):
        if self.is_premium:
            return 10 + max(0, days_overdrawn - 7) * 0.85
        return days_overdrawn * 1.75
```

## 什么时候该移动

- **Feature Envy.** 最明显的信号：一个函数用别的对象的数据，比用自己的数据还多。见 [feature-envy.md](./feature-envy.md) 里这种 smell 的修法通常就是 Move Function - 把行为搬到它所嫉妒的数据所在的对象上。这遵循 GRASP 的 Information Expert 思路：把行为放到信息所在处（`../design-principles/grasp.md`）。
- **耦合方向。** 当 module A 里的函数高度依赖 module B，却几乎不依赖它自己所属的 module 时，依赖箭头和代码所在位置在打架。把函数移到 B，可以把依赖图拉直并减少耦合。
- **共变更。** 当一个函数总是和另一个模块里的代码一起变化 - 每次 commit 都一起改 - 它们多半本来就该放在一起。这是 [shotgun-surgery.md](./shotgun-surgery.md) 所提示的那种情况，指向的是收拢。

## 安全地移动

先判断函数当前上下文到底给了它什么。如果它只使用目标对象的数据，移动就很干净。如果它同时跨着两边，可能需要先拆开（先提取出属于另一边的部分，再只移动那部分），或者把剩余上下文作为参数传过去。看看它调用了什么、又被什么调用 - 把它移走可能会反转依赖，或者制造循环，而这本身就是在告诉你这个移动是否合理。

每一步都要保留行为，并且跑测试；见 [safe-refactoring.md](./safe-refactoring.md)。在 Python 里，还要更新 imports，并注意迁移后引入的 circular-import 风险。

## 迁移期间保留旧 API

当这个函数属于公开或广泛使用的接口时，不要一刀切地破坏调用方。先把主体移动到新位置，然后在旧位置留一个委托函数，把调用转发过去。这个委托在过渡期里暂时是一个 [thin-wrapper-function.md](./thin-wrapper-function.md)，这没问题 - 它的存在是为了在调用方迁移期间保持旧 API 稳定。等所有调用方都指向新位置后（用 `rg` 找出来），再删掉这个委托。若有弃用窗口，就在旧路径上加 warning，让调用方知道该更新了。

## 何时不要移动

如果一个函数确实是平衡地使用了多个对象的数据，那就未必有单一更好的拥有者 - 强行移动只会把耦合换个地方而已。而且，如果所谓“更好的拥有者”其实只是一个只放数据的对象（DTO、ORM row、config object），本来就应该保持无行为，那把行为塞进去就会破坏这个边界；关于这条边界在哪里，见 `tell-dont-ask.md`。
