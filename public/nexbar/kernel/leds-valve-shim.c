// SPDX-License-Identifier: GPL-2.0+
// Derived from rpf16rj/steamos-led-bar-release leds-valve-shim.c.

#include <linux/device.h>
#include <linux/fs.h>
#include <linux/kstrtox.h>
#include <linux/led-class-multicolor.h>
#include <linux/miscdevice.h>
#include <linux/mutex.h>
#include <linux/platform_device.h>
#include <linux/poll.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/stringify.h>
#include <linux/sysfs.h>
#include <linux/timekeeping.h>
#include <linux/uaccess.h>
#include <linux/wait.h>

#define DRVNAME "valve-leds-shim"
#define VALVE_NUM_LEDS 17
#define VALVE_NUM_COMPONENTS 3
#define VALVE_LEDS_UAPI_MAGIC 0x564c4544
#define VALVE_LEDS_UAPI_VERSION 1
#define VALVE_BRIGHTNESS_MAX 255
#define VALVE_DELAY_MAX 20

struct valve_leds_pixel {
    u8 r, g, b, brightness;
};

struct valve_leds_snapshot {
    u32 magic;
    u16 version;
    u16 size;
    u64 seq;
    u64 monotonic_ns;
    u8 enabled;
    u8 effect;
    u8 brightness_scale;
    u8 delay;
    u8 breath_offset;
    u8 breath_level;
    u8 patrol_num;
    u8 color_shift;
    struct valve_leds_pixel pixels[VALVE_NUM_LEDS];
} __packed;

enum valve_effect {
    EFFECT_OFF = 0,
    EFFECT_MANUAL,
    EFFECT_NORMAL,
    EFFECT_RAINBOW,
    EFFECT_BREATH,
    EFFECT_PATROL,
    EFFECT_FACTORY,
    EFFECT_DEMO,
};

static const char *const effect_names[] = {
    "off", "manual", "normal", "rainbow", "breath", "patrol", "factory", "demo"
};

struct valve_led {
    struct led_classdev_mc mcdev;
    struct mc_subled rgb[VALVE_NUM_COMPONENTS];
    int index;
    u8 brightness;
};

struct valve_leds {
    struct platform_device *pdev;
    struct miscdevice miscdev;
    struct mutex lock;
    wait_queue_head_t waitq;
    u64 seq;
    u64 monotonic_ns;
    struct valve_led leds[VALVE_NUM_LEDS];
    bool enabled;
    u8 effect;
    u8 brightness_scale;
    u8 delay;
    u8 breath_offset;
    u8 breath_level;
    u8 patrol_num;
    u8 color_shift;
    u8 brightness_startup;
    u8 multi_intensity_startup[3];
};

struct valve_file {
    struct valve_leds *leds;
    u64 last_seen_seq;
};

static struct valve_leds *active_leds;
static struct platform_device *shim_pdev;
static bool debug_log;
module_param(debug_log, bool, 0644);

static void state_changed(struct valve_leds *leds)
{
    leds->seq++;
    leds->monotonic_ns = ktime_get_ns();
    wake_up_interruptible(&leds->waitq);
}

static ssize_t enabled_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct valve_leds *leds = dev_get_drvdata(dev->parent);
    return sysfs_emit(buf, "%u\n", leds->enabled ? 1 : 0);
}

static ssize_t enabled_store(struct device *dev, struct device_attribute *attr,
                             const char *buf, size_t count)
{
    struct valve_leds *leds = dev_get_drvdata(dev->parent);
    bool value;
    if (kstrtobool(buf, &value))
        return -EINVAL;
    mutex_lock(&leds->lock);
    leds->enabled = value;
    state_changed(leds);
    mutex_unlock(&leds->lock);
    return count;
}

static ssize_t effect_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct valve_leds *leds = dev_get_drvdata(dev->parent);
    if (leds->effect >= ARRAY_SIZE(effect_names))
        return -EINVAL;
    return sysfs_emit(buf, "%s\n", effect_names[leds->effect]);
}

static ssize_t effect_store(struct device *dev, struct device_attribute *attr,
                            const char *buf, size_t count)
{
    struct valve_leds *leds = dev_get_drvdata(dev->parent);
    int value = __sysfs_match_string(effect_names, ARRAY_SIZE(effect_names), buf);
    if (value < 0)
        return value;
    mutex_lock(&leds->lock);
    leds->effect = value;
    state_changed(leds);
    mutex_unlock(&leds->lock);
    return count;
}

static ssize_t effect_index_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    ssize_t len = 0;
    int i;
    for (i = 0; i < ARRAY_SIZE(effect_names); i++)
        len += sysfs_emit_at(buf, len, "%s%s", i ? " " : "", effect_names[i]);
    return len + sysfs_emit_at(buf, len, "\n");
}

static ssize_t delay_range_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    return sysfs_emit(buf, "0-%u\n", VALVE_DELAY_MAX);
}

struct byte_attr {
    struct device_attribute devattr;
    size_t offset;
    unsigned int max;
};

static ssize_t byte_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct valve_leds *leds = dev_get_drvdata(dev->parent);
    struct byte_attr *ba = container_of(attr, struct byte_attr, devattr);
    u8 value;
    mutex_lock(&leds->lock);
    value = *(u8 *)((char *)leds + ba->offset);
    mutex_unlock(&leds->lock);
    return sysfs_emit(buf, "0x%02x\n", value);
}

static ssize_t byte_store(struct device *dev, struct device_attribute *attr,
                          const char *buf, size_t count)
{
    struct valve_leds *leds = dev_get_drvdata(dev->parent);
    struct byte_attr *ba = container_of(attr, struct byte_attr, devattr);
    unsigned int value;
    if (kstrtouint(buf, 0, &value) || value > ba->max)
        return -EINVAL;
    mutex_lock(&leds->lock);
    *(u8 *)((char *)leds + ba->offset) = value;
    state_changed(leds);
    mutex_unlock(&leds->lock);
    return count;
}

#define BYTE_ATTR(name, maximum) \
    static struct byte_attr dev_attr_##name = { \
        .devattr = __ATTR(name, 0644, byte_show, byte_store), \
        .offset = offsetof(struct valve_leds, name), \
        .max = maximum, \
    }

BYTE_ATTR(delay, VALVE_DELAY_MAX);
BYTE_ATTR(breath_offset, 255);
BYTE_ATTR(breath_level, 255);
BYTE_ATTR(patrol_num, 255);
BYTE_ATTR(color_shift, 255);
BYTE_ATTR(brightness_scale, 255);
BYTE_ATTR(brightness_startup, 255);

static ssize_t multi_intensity_startup_show(struct device *dev,
        struct device_attribute *attr, char *buf)
{
    struct valve_leds *leds = dev_get_drvdata(dev->parent);
    return sysfs_emit(buf, "%u %u %u\n",
                      leds->multi_intensity_startup[0],
                      leds->multi_intensity_startup[1],
                      leds->multi_intensity_startup[2]);
}

static ssize_t multi_intensity_startup_store(struct device *dev,
        struct device_attribute *attr, const char *buf, size_t count)
{
    struct valve_leds *leds = dev_get_drvdata(dev->parent);
    unsigned int r, g, b;
    if (sscanf(buf, "%u %u %u", &r, &g, &b) != 3 || r > 255 || g > 255 || b > 255)
        return -EINVAL;
    mutex_lock(&leds->lock);
    leds->multi_intensity_startup[0] = r;
    leds->multi_intensity_startup[1] = g;
    leds->multi_intensity_startup[2] = b;
    state_changed(leds);
    mutex_unlock(&leds->lock);
    return count;
}

static DEVICE_ATTR_RW(enabled);
static DEVICE_ATTR_RW(effect);
static DEVICE_ATTR_RO(effect_index);
static DEVICE_ATTR_RO(delay_range);
static DEVICE_ATTR_RW(multi_intensity_startup);

static struct attribute *global_attrs[] = {
    &dev_attr_enabled.attr,
    &dev_attr_effect.attr,
    &dev_attr_effect_index.attr,
    &dev_attr_delay_range.attr,
    &dev_attr_delay.devattr.attr,
    &dev_attr_breath_offset.devattr.attr,
    &dev_attr_breath_level.devattr.attr,
    &dev_attr_patrol_num.devattr.attr,
    &dev_attr_color_shift.devattr.attr,
    &dev_attr_brightness_scale.devattr.attr,
    &dev_attr_brightness_startup.devattr.attr,
    &dev_attr_multi_intensity_startup.attr,
    NULL,
};

static const struct attribute_group global_group = { .attrs = global_attrs };

static int valve_set_brightness(struct led_classdev *cdev, enum led_brightness brightness)
{
    struct led_classdev_mc *mcdev = lcdev_to_mccdev(cdev);
    struct valve_led *led = container_of(mcdev, struct valve_led, mcdev);
    struct valve_leds *leds = dev_get_drvdata(cdev->dev->parent);
    mutex_lock(&leds->lock);
    led_mc_calc_color_components(mcdev, brightness);
    led->brightness = brightness;
    state_changed(leds);
    mutex_unlock(&leds->lock);
    return 0;
}

static void fill_snapshot(struct valve_leds *leds, struct valve_leds_snapshot *snap)
{
    int i;
    memset(snap, 0, sizeof(*snap));
    snap->magic = VALVE_LEDS_UAPI_MAGIC;
    snap->version = VALVE_LEDS_UAPI_VERSION;
    snap->size = sizeof(*snap);
    snap->seq = leds->seq;
    snap->monotonic_ns = leds->monotonic_ns;
    snap->enabled = leds->enabled;
    snap->effect = leds->effect;
    snap->brightness_scale = leds->brightness_scale;
    snap->delay = leds->delay;
    snap->breath_offset = leds->breath_offset;
    snap->breath_level = leds->breath_level;
    snap->patrol_num = leds->patrol_num;
    snap->color_shift = leds->color_shift;
    for (i = 0; i < VALVE_NUM_LEDS; i++) {
        snap->pixels[i].r = leds->leds[i].rgb[0].intensity;
        snap->pixels[i].g = leds->leds[i].rgb[1].intensity;
        snap->pixels[i].b = leds->leds[i].rgb[2].intensity;
        snap->pixels[i].brightness = leds->leds[i].brightness;
    }
}

static int shim_open(struct inode *inode, struct file *file)
{
    struct valve_file *ctx;
    if (!active_leds)
        return -ENODEV;
    ctx = kzalloc(sizeof(*ctx), GFP_KERNEL);
    if (!ctx)
        return -ENOMEM;
    ctx->leds = active_leds;
    file->private_data = ctx;
    return 0;
}

static int shim_release(struct inode *inode, struct file *file)
{
    kfree(file->private_data);
    return 0;
}

static ssize_t shim_read(struct file *file, char __user *buf, size_t count, loff_t *ppos)
{
    struct valve_file *ctx = file->private_data;
    struct valve_leds_snapshot snap;
    if (!ctx || !ctx->leds)
        return -ENODEV;
    if (count < sizeof(snap))
        return -EINVAL;
    mutex_lock(&ctx->leds->lock);
    fill_snapshot(ctx->leds, &snap);
    ctx->last_seen_seq = snap.seq;
    mutex_unlock(&ctx->leds->lock);
    if (copy_to_user(buf, &snap, sizeof(snap)))
        return -EFAULT;
    return sizeof(snap);
}

static __poll_t shim_poll(struct file *file, poll_table *wait)
{
    struct valve_file *ctx = file->private_data;
    __poll_t mask = 0;
    u64 seq;
    if (!ctx || !ctx->leds)
        return EPOLLERR;
    poll_wait(file, &ctx->leds->waitq, wait);
    mutex_lock(&ctx->leds->lock);
    seq = ctx->leds->seq;
    mutex_unlock(&ctx->leds->lock);
    if (seq != ctx->last_seen_seq)
        mask |= EPOLLIN | EPOLLRDNORM;
    return mask;
}

static const struct file_operations shim_fops = {
    .owner = THIS_MODULE,
    .open = shim_open,
    .release = shim_release,
    .read = shim_read,
    .poll = shim_poll,
    .llseek = noop_llseek,
};

static int shim_probe(struct platform_device *pdev)
{
    struct valve_leds *leds;
    int i, c, ret;
    leds = devm_kzalloc(&pdev->dev, sizeof(*leds), GFP_KERNEL);
    if (!leds)
        return -ENOMEM;
    leds->pdev = pdev;
    mutex_init(&leds->lock);
    init_waitqueue_head(&leds->waitq);
    leds->seq = 1;
    leds->monotonic_ns = ktime_get_ns();
    leds->enabled = true;
    leds->effect = EFFECT_OFF;
    leds->brightness_scale = 56;
    leds->delay = 8;
    leds->breath_offset = 4;
    leds->breath_level = 32;
    leds->patrol_num = 3;
    leds->color_shift = 5;
    leds->brightness_startup = 56;
    leds->multi_intensity_startup[2] = 255;
    platform_set_drvdata(pdev, leds);

    for (i = 0; i < VALVE_NUM_LEDS; i++) {
        for (c = 0; c < VALVE_NUM_COMPONENTS; c++) {
            leds->leds[i].rgb[c].color_index = LED_COLOR_ID_RED + c;
            leds->leds[i].rgb[c].brightness = 255;
            leds->leds[i].rgb[c].channel = c;
            leds->leds[i].rgb[c].intensity = 0;
        }
        leds->leds[i].index = i;
        leds->leds[i].brightness = 255;
        leds->leds[i].mcdev.led_cdev.name = devm_kasprintf(&pdev->dev, GFP_KERNEL,
                                                           "valve-leds[%d]", i);
        if (!leds->leds[i].mcdev.led_cdev.name)
            return -ENOMEM;
        leds->leds[i].mcdev.led_cdev.max_brightness = 255;
        leds->leds[i].mcdev.led_cdev.brightness = 255;
        leds->leds[i].mcdev.led_cdev.brightness_set_blocking = valve_set_brightness;
        leds->leds[i].mcdev.num_colors = 3;
        leds->leds[i].mcdev.subled_info = leds->leds[i].rgb;
        ret = devm_led_classdev_multicolor_register(&pdev->dev, &leds->leds[i].mcdev);
        if (ret)
            return ret;
        ret = devm_device_add_group(leds->leds[i].mcdev.led_cdev.dev, &global_group);
        if (ret)
            return ret;
    }

    leds->miscdev.minor = MISC_DYNAMIC_MINOR;
    leds->miscdev.name = "valve-leds-shim";
    leds->miscdev.fops = &shim_fops;
    leds->miscdev.parent = &pdev->dev;
    leds->miscdev.mode = 0444;
    active_leds = leds;
    ret = misc_register(&leds->miscdev);
    if (ret) {
        active_leds = NULL;
        return ret;
    }
    dev_info(&pdev->dev, "NexBar Valve-compatible LED shim registered\n");
    return 0;
}

static void shim_remove(struct platform_device *pdev)
{
    active_leds = NULL;
    misc_deregister(&((struct valve_leds *)platform_get_drvdata(pdev))->miscdev);
}

static struct platform_driver shim_driver = {
    .probe = shim_probe,
    .remove = shim_remove,
    .driver = { .name = DRVNAME },
};

static int __init shim_init(void)
{
    int ret = platform_driver_register(&shim_driver);
    if (ret)
        return ret;
    shim_pdev = platform_device_register_simple(DRVNAME, -1, NULL, 0);
    if (IS_ERR(shim_pdev)) {
        ret = PTR_ERR(shim_pdev);
        platform_driver_unregister(&shim_driver);
        return ret;
    }
    return 0;
}

static void __exit shim_exit(void)
{
    platform_device_unregister(shim_pdev);
    platform_driver_unregister(&shim_driver);
}

module_init(shim_init);
module_exit(shim_exit);

MODULE_AUTHOR("Valve Corporation");
MODULE_AUTHOR("Anna Oake");
MODULE_AUTHOR("NexBar contributors");
MODULE_DESCRIPTION("Valve-compatible virtual 17-LED front bar shim for NexBar");
MODULE_LICENSE("GPL");
