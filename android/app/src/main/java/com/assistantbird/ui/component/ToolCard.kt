package com.assistantbird.ui.component

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistantbird.model.ToolCardData
import com.assistantbird.ui.theme.*

@Composable
fun ToolCardItem(card: ToolCardData, modifier: Modifier = Modifier) {
    var expanded by remember { mutableStateOf(card.output != null) }

    LaunchedEffect(card.output) {
        if (card.output != null) expanded = true
    }

    Column(
        modifier = modifier
            .widthIn(max = 340.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(ToolCard)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { expanded = !expanded }
                .padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = if (card.output != null) Icons.Default.CheckCircle else Icons.Default.Build,
                contentDescription = null,
                tint = if (card.output != null) Success else Accent,
                modifier = Modifier.size(14.dp),
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = card.name,
                color = TextSecondary,
                fontSize = 12.sp,
                modifier = Modifier.weight(1f),
            )
            Icon(
                imageVector = Icons.Default.ExpandMore,
                contentDescription = "展开",
                tint = TextMuted,
                modifier = Modifier
                    .size(16.dp)
                    .rotate(if (expanded) 180f else 0f),
            )
        }

        AnimatedVisibility(visible = expanded) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(BgPrimary)
                    .padding(10.dp)
            ) {
                if (card.output != null) {
                    Text(
                        text = card.output!!,
                        color = TextSecondary,
                        fontSize = 12.sp,
                        lineHeight = 18.sp,
                    )
                } else {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(12.dp),
                            strokeWidth = 1.5.dp,
                            color = Accent,
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("运行中…", color = TextMuted, fontSize = 12.sp)
                    }
                }
            }
        }
    }
}
